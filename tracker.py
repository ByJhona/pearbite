from threading import Thread
from socket import socket, AF_INET, SOCK_STREAM
import json
from gerenciadorUsuario import GerenciadorUsuarios
from util import receber_json, enviar_json, gerar_par_chaves, descriptografar_mensagem, criptografar_mensagem

# ESTRUTURAS DE DADOS AMPLIADAS
usuarios_ativos = {} # Mantém informações de conexão dos usuários
salas = {} # Dicionário para gerenciar salas e seus membros: {"nome_sala": ["user1", "user2"]}

chave_privada = None
chave_publica = None

def configurar_servidor(porta) -> socket:
    servSocket = socket(AF_INET, SOCK_STREAM)
    servSocket.bind(('', porta))
    servSocket.listen(5)
    print(f"Servidor ouvindo na porta {porta}...")
    return servSocket

def deslogar_usuario(endereco):
    global usuarios_ativos, salas
    nome_usuario_deslogado = None
    for nome, info in list(usuarios_ativos.items()):
        if info['ENDERECO'] == endereco:
            nome_usuario_deslogado = nome
            del usuarios_ativos[nome]
            break
    
    # Remove o usuário de qualquer sala em que ele esteja
    if nome_usuario_deslogado:
        for nome_sala, membros in list(salas.items()):
            if nome_usuario_deslogado in membros:
                membros.remove(nome_usuario_deslogado)
                # Se a sala ficar vazia, remove a sala
                if not membros:
                    del salas[nome_sala]
                else:
                    # Notifica outros membros que o usuário saiu (opcional)
                    pass


def broadcast_atualizacao_sala(nome_sala):
    """
    Envia uma lista atualizada de membros para todos na sala.
    """
    if nome_sala in salas:
        membros_da_sala = list(salas[nome_sala]["membros"]) # Cria uma cópia da lista
        for membro_destino in membros_da_sala:
            # Prepara uma lista personalizada para cada membro, contendo os outros
            outros_membros_info = [
                {"usuario": u, "chave": usuarios_ativos[u]["CHAVE_PUBLICA"]}
                for u in membros_da_sala
                if u != membro_destino and u in usuarios_ativos
            ]
            
            # Monta e envia a mensagem de atualização para o membro de destino
            if membro_destino in usuarios_ativos:
                msg_atualizacao = {"STATUS": "ATUALIZACAO_SALA", "MEMBROS": outros_membros_info, "SALA": nome_sala}
                enviar_json(usuarios_ativos[membro_destino]['CONEXAO'], msg_atualizacao)

def lidar_requisicao(conexao: socket, endereco,gerenciadorUsuarios: GerenciadorUsuarios):
    global usuarios_ativos, salas, chave_privada, chave_publica
    enviar_json(conexao, {"STATUS":"CHAVE_PUBLICA", "CHAVE_PUBLICA":chave_publica})
    print(f"Conexão iniciada com {endereco}")
    nome_usuario_thread = None

    try:
        while True:
            json_recebido = receber_json(conexao)
            if not json_recebido: break

            operacao = json_recebido.get('CMD', '')
            usuario_logado = nome_usuario_thread

            match operacao:
                case 'LOGIN':
                    nome_cript, senha_cript, chave_publica_peer = json_recebido.get('NOME'), json_recebido.get('SENHA'), json_recebido.get('CHAVE_PUBLICA')
                    nome = descriptografar_mensagem(nome_cript, chave_privada)
                    senha = descriptografar_mensagem(senha_cript, chave_privada)
                    
                    if gerenciadorUsuarios.login(nome, senha):
                        nome_usuario_thread = nome
                        usuarios_ativos[nome] = {'ENDERECO': endereco, 'CONEXAO': conexao, "CHAVE_PUBLICA": chave_publica_peer }
                        enviar_json(conexao, {"STATUS": "LOGIN_REALIZADO", "NOME": nome})
                    else:
                        enviar_json(conexao, {"STATUS": "LOGIN_FALHOU"})
                
                case 'DESLOGAR':
                    if json_recebido.get('NOME') in usuarios_ativos: break

                case 'CADASTRAR':
                    nome_cript_peer, senha_cript_peer = json_recebido.get('NOME'), json_recebido.get('SENHA')
                    nome = descriptografar_mensagem(nome_cript_peer, chave_privada)
                    senha = descriptografar_mensagem(senha_cript_peer, chave_privada)

                    status = "CADASTRO_REALIZADO" if gerenciadorUsuarios.cadastrar(nome, senha) else "CADASTRO_FALHOU"
                    enviar_json(conexao, {"STATUS": status, "NOME":nome})

                case 'LISTAR_PEERS':
                    if not usuario_logado: continue
                    lista = [{"usuario": n, "chave": usuarios_ativos[n]["CHAVE_PUBLICA"]} for n in usuarios_ativos if n != usuario_logado]
                    enviar_json(conexao, {"STATUS": "OK", "PEERS": lista})

                case 'LISTAR_SALAS':
                    if not usuario_logado: continue
                    lista_salas = [{"nome": n, "moderador": d["moderador"], "membros": len(d["membros"])} for n, d in salas.items()]
                    enviar_json(conexao, {"STATUS": "OK", "SALAS": lista_salas})

                case 'ENVIAR_MSG':
                    if not usuario_logado: continue
                    destinatario, payload = json_recebido.get('DESTINATARIO'), json_recebido.get('PAYLOAD')
                    if destinatario in usuarios_ativos:
                        msg = {"STATUS": "MSG_DIRETA", "REMETENTE": usuario_logado, "PAYLOAD": payload}
                        enviar_json(usuarios_ativos[destinatario]['CONEXAO'], msg)
                case 'ENVIAR_MSG_SALA':
                    if not usuario_logado: continue
                    destinatario, payload,sala = json_recebido.get('DESTINATARIO'), json_recebido.get('PAYLOAD'),json_recebido.get('SALA')
                    if destinatario in usuarios_ativos:
                        msg = {"STATUS": "MSG_SALA", "REMETENTE": usuario_logado, "PAYLOAD": payload, "SALA":sala}
                        enviar_json(usuarios_ativos[destinatario]['CONEXAO'], msg)
                case 'CRIAR_SALA':
                    if not usuario_logado: continue
                    nome_sala = json_recebido.get('SALA')
                    senha_sala = json_recebido.get('SENHA')
                    if nome_sala in salas:
                        enviar_json(conexao, {"STATUS": "ERRO", "MENSAGEM": "Sala já existe."})
                    else:
                        salas[nome_sala] = {"membros": [usuario_logado], "moderador": usuario_logado}
                        enviar_json(conexao, {"STATUS": "SALA_CRIADA", "SALA": nome_sala})
                        broadcast_atualizacao_sala(nome_sala)
                case "EXPULSAR_USUARIO":
                    nome_sala = json_recebido.get("SALA")
                    usuario_alvo = json_recebido.get("ALVO")

                    if nome_sala not in salas:
                        enviar_json(conexao, {"STATUS": "ERRO", "MENSAGEM": "Sala não encontrada."})

                    elif salas[nome_sala]["moderador"] != nome_usuario_thread:
                        enviar_json(conexao, {"STATUS": "ERRO", "MENSAGEM": "Apenas o administrador pode expulsar membros."})

                    elif usuario_alvo in salas[nome_sala]["membros"]:
                        salas[nome_sala]["membros"].remove(usuario_alvo)
                        if usuario_alvo in usuarios_ativos:
                            enviar_json(usuarios_ativos[usuario_alvo]["CONEXAO"], {
                                "STATUS": "EXPULSO",
                                "SALA": nome_sala,
                                "MENSAGEM": f"Você foi expulso da sala {nome_sala}."
                            })
                        for membro in salas[nome_sala]["membros"]:
                            if membro != usuario_alvo and membro in usuarios_ativos:
                                enviar_json(usuarios_ativos[membro]["CONEXAO"], {
                                    "STATUS": "USUARIO_EXPULSO",
                                    "SALA": nome_sala,
                                    "ALVO": usuario_alvo
                                })

                        broadcast_atualizacao_sala(nome_sala)

                    else:
                        enviar_json(conexao, {"STATUS": "ERRO", "MENSAGEM": "Usuário não está na sala."})


                case 'ENTRAR_SALA':
                    if not usuario_logado: continue
                    nome_sala = json_recebido.get('SALA')
                    if nome_sala in salas:
                        salas[nome_sala]["membros"].append(usuario_logado)
                        enviar_json(conexao, {"STATUS": "ENTROU_NA_SALA", "SALA": nome_sala})
                        broadcast_atualizacao_sala(nome_sala)
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
                case _:
                    print(f"Comando desconhecido: {operacao}")
    finally:
        if nome_usuario_thread:
            print(f"Deslogando {nome_usuario_thread}...")
            sala_do_usuario = None
            for nome_sala, dados in list(salas.items()):
                if nome_usuario_thread in dados["membros"]:
                    sala_do_usuario = nome_sala
                    dados["membros"].remove(nome_usuario_thread)
                    if not dados["membros"]: del salas[nome_sala]
                    break
            
            if nome_usuario_thread in usuarios_ativos: del usuarios_ativos[nome_usuario_thread]
            
            if sala_do_usuario: broadcast_atualizacao_sala(sala_do_usuario)
        
        conexao.close()
        print(f"Conexão encerrada com {endereco}")

def iniciar_servidor():
    global chave_privada, chave_publica
    chave_privada, chave_publica = gerar_par_chaves()
    servidor = configurar_servidor(12001)
    gerenciadorUsuarios = GerenciadorUsuarios()

    while True:
        conexao, endereco = servidor.accept()
        thread = Thread(target=lidar_requisicao, args=(
            conexao, endereco, gerenciadorUsuarios))
        thread.start()


def main():
    iniciar_servidor()


if __name__ == '__main__':
    main()