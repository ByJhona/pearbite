from threading import Thread
from socket import socket, AF_INET, SOCK_STREAM
import json
from gerenciadorUsuario import GerenciadorUsuarios, GerenciadorSalas, Sala
from util import receber_json, enviar_json

# ESTRUTURAS DE DADOS
usuarios_ativos = {}  # Mantém informações de conexão dos usuários
chaves_publicas = {}  # Armazena a chave pública de cada usuário
salas = {}  # Dicionário para gerenciar salas e seus membros: {"nome_sala": {"membros": [], "moderador": "nome"}}

def carregar_salas_do_arquivo(gerenciadorSalas):
    global salas
    salas_carregadas = gerenciadorSalas.listar_salas()
    for sala in salas_carregadas:
        salas[sala.nome] = {"membros": [], "moderador": sala.moderador}
    print(f"Carregadas {len(salas_carregadas)} salas do arquivo")

def configurar_servidor(porta) -> socket:
    servSocket = socket(AF_INET, SOCK_STREAM)
    servSocket.bind(('', porta))
    servSocket.listen(5)
    print(f"Servidor ouvindo na porta {porta}...")
    return servSocket

def deslogar_usuario(endereco):
    global usuarios_ativos, chaves_publicas, salas
    nome_usuario_deslogado = None
    for nome, info in list(usuarios_ativos.items()):
        if info['ENDERECO'] == endereco:
            nome_usuario_deslogado = nome
            del usuarios_ativos[nome]
            if nome in chaves_publicas:
                del chaves_publicas[nome]
            break
    
    if nome_usuario_deslogado:
        for nome_sala, dados in list(salas.items()):
            if nome_usuario_deslogado in dados["membros"]:
                dados["membros"].remove(nome_usuario_deslogado)
                if not dados["membros"]:
                    del salas[nome_sala]

def broadcast_atualizacao_sala(nome_sala):
    if nome_sala in salas:
        membros_da_sala = list(salas[nome_sala]["membros"])
        for membro_destino in membros_da_sala:
            outros_membros_info = [
                {"usuario": u, "chave": chaves_publicas.get(u)}
                for u in membros_da_sala
                if u != membro_destino and u in chaves_publicas
            ]
            
            if membro_destino in usuarios_ativos:
                msg_atualizacao = {"TIPO": "ATUALIZACAO_SALA", "MEMBROS": outros_membros_info}
                enviar_json(usuarios_ativos[membro_destino]['CONEXAO'], msg_atualizacao)

def lidar_requisicao(conexao: socket, endereco, gerenciadorUsuarios: GerenciadorUsuarios, gerenciadorSalas: GerenciadorSalas):
    print(f"Conexão iniciada com {endereco}")
    global usuarios_ativos, chaves_publicas, salas
    nome_usuario_thread = None

    try:
        while True:
            json_recebido = receber_json(conexao)
            if not json_recebido: break

            operacao = json_recebido.get('CMD', '')
            usuario_logado = nome_usuario_thread

            match operacao:
                case 'LOGIN':
                    nome = json_recebido.get('NOME')
                    senha = json_recebido.get('SENHA')
                    chave_publica = json_recebido.get('CHAVE_PUBLICA')
                    if gerenciadorUsuarios.login(nome, senha):
                        nome_usuario_thread = nome
                        usuarios_ativos[nome] = {'ENDERECO': endereco, 'CONEXAO': conexao}
                        chaves_publicas[nome] = chave_publica
                        enviar_json(conexao, {"STATUS": "LOGIN_REALIZADO", "NOME": nome})
                    else:
                        enviar_json(conexao, {"STATUS": "LOGIN_FALHOU"})
                
                case 'DESLOGAR':
                    nome = json_recebido.get('NOME')
                    if nome in usuarios_ativos:
                        deslogar_usuario(endereco)
                        break

                case 'CADASTRAR':
                    nome = json_recebido.get('NOME')
                    senha = json_recebido.get('SENHA')
                    status = "CADASTRO_REALIZADO" if gerenciadorUsuarios.cadastrar(nome, senha) else "CADASTRO_FALHOU"
                    enviar_json(conexao, {"STATUS": status})

                case 'LISTAR_PEERS':
                    if not usuario_logado: continue
                    lista = [{"usuario": n, "chave": chaves_publicas.get(n)} for n in usuarios_ativos if n != usuario_logado]
                    enviar_json(conexao, {"STATUS": "OK", "PEERS": lista})

                case 'LISTAR_SALAS':
                    if not usuario_logado: continue
                    lista_salas = [{"nome": n, "moderador": d["moderador"], "membros": len(d["membros"])} for n, d in salas.items()]
                    enviar_json(conexao, {"STATUS": "OK", "SALAS": lista_salas})

                case 'ENVIAR_MSG':
                    if not usuario_logado: continue
                    destinatario = json_recebido.get('DESTINATARIO')
                    payload = json_recebido.get('PAYLOAD')
                    if destinatario in usuarios_ativos:
                        msg = {
                            "TIPO": "MSG_DIRETA",
                            "REMETENTE": usuario_logado,
                            "PAYLOAD": payload
                        }
                        enviar_json(usuarios_ativos[destinatario]['CONEXAO'], msg)
                
                case 'CRIAR_SALA':
                    if not usuario_logado: continue
                    nome_sala = json_recebido.get('SALA')
                    hash_senha = gerenciadorUsuarios.obter_hash_senha(usuario_logado)
                    if not hash_senha:
                        enviar_json(conexao, {"STATUS": "ERRO", "MENSAGEM": "Hash do usuário não encontrado."})
                        break

                    nova_sala = Sala(nome_sala, usuario_logado, hash_senha)
                    gerenciadorSalas.salvar_sala(nova_sala)
                    salas[nome_sala] = {"membros": [usuario_logado], "moderador": usuario_logado}
                    enviar_json(conexao, {"STATUS": "SALA_CRIADA", "SALA": nome_sala})
                    broadcast_atualizacao_sala(nome_sala)

                case 'ENTRAR_SALA':
                    if not usuario_logado: continue
                    nome_sala = json_recebido.get('SALA')
                    senha = json_recebido.get('SENHA', '')
                    if nome_sala in salas:
                        if gerenciadorSalas.validar_moderador(nome_sala, senha):
                            salas[nome_sala]["membros"].append(usuario_logado)
                            enviar_json(conexao, {"STATUS": "ENTROU_NA_SALA", "SALA": nome_sala})
                            broadcast_atualizacao_sala(nome_sala)
                        else:
                            enviar_json(conexao, {"STATUS": "ERRO", "MENSAGEM": "Senha incorreta."})
                    else:
                        enviar_json(conexao, {"STATUS": "ERRO", "MENSAGEM": "Sala não existe."})

                case 'SAIR_SALA':
                    if not usuario_logado: continue
                    nome_sala = json_recebido.get('SALA')
                    if nome_sala in salas and usuario_logado in salas[nome_sala]["membros"]:
                        salas[nome_sala]["membros"].remove(usuario_logado)
                        enviar_json(conexao, {"STATUS": "SAIU_DA_SALA"})
                        if not salas[nome_sala]["membros"]:
                            del salas[nome_sala]
                        else:
                            broadcast_atualizacao_sala(nome_sala)

                case 'REMOVER_SALA':
                    if not usuario_logado: continue
                    nome_sala = json_recebido.get('SALA')
                    senha = json_recebido.get('SENHA')
                    if gerenciadorSalas.remover_sala(nome_sala, senha):
                        if nome_sala in salas:
                            del salas[nome_sala]
                        enviar_json(conexao, {"STATUS": "SALA_REMOVIDA"})
                    else:
                        enviar_json(conexao, {"STATUS": "ERRO", "MENSAGEM": "Falha ao remover sala."})

                case 'EXPULSAR_USUARIO':
                    if not usuario_logado: continue
                    nome_sala = json_recebido.get('SALA')
                    usuario_expulsar = json_recebido.get('USUARIO')
                    senha = json_recebido.get('SENHA')
                    
                    if nome_sala in salas and salas[nome_sala]["moderador"] == usuario_logado:
                        if gerenciadorSalas.validar_moderador(nome_sala, senha):
                            if usuario_expulsar in salas[nome_sala]["membros"]:
                                salas[nome_sala]["membros"].remove(usuario_expulsar)
                                if usuario_expulsar in usuarios_ativos:
                                    enviar_json(usuarios_ativos[usuario_expulsar]['CONEXAO'], 
                                              {"STATUS": "EXPULSO", "SALA": nome_sala})
                                broadcast_atualizacao_sala(nome_sala)
                        else:
                            enviar_json(conexao, {"STATUS": "ERRO", "MENSAGEM": "Senha incorreta."})

                case _:
                    print(f"Comando desconhecido: {operacao}")
    finally:
        if nome_usuario_thread:
            print(f"Deslogando {nome_usuario_thread}...")
            deslogar_usuario(endereco)
        conexao.close()
        print(f"Conexão encerrada com {endereco}")

def iniciar_servidor():
    servidor = configurar_servidor(12001)
    gerenciadorUsuarios = GerenciadorUsuarios()
    gerenciadorSalas = GerenciadorSalas()
    carregar_salas_do_arquivo(gerenciadorSalas)

    while True:
        conexao, endereco = servidor.accept()
        thread = Thread(target=lidar_requisicao, args=(
            conexao, endereco, gerenciadorUsuarios, gerenciadorSalas))
        thread.start()

def main():
    iniciar_servidor()

if __name__ == '__main__':
    main()