import socket
import json
import sys
import threading
import base64 
from util import receber_json, enviar_json, criptografar_mensagem, descriptografar_mensagem, gerar_par_chaves
import os
from datetime import datetime
import time

# --- Variáveis de Estado Globais ---
usuario_logado = None
cliente_socket = None
cache_salas = {}
sala_atual = None
chat_atual = None

# As variáveis de chave agora armazenarão a chave real
chave_privada = None
chave_publica = None
chave_publica_servidor = None

chaves_peers_cache = {}


def monitorar_historico(arquivo, parar_evento):
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            f.seek(0, os.SEEK_END)
            while not parar_evento.is_set():
                linha = f.readline()
                if linha:
                    print(f"\n{linha.strip()}")
                else:
                    time.sleep(0.5)
    except FileNotFoundError:
        print(f"[ERRO] Arquivo {arquivo} não encontrado.")

def exibir_historico(caminho_arquivo):
    if os.path.exists(caminho_arquivo):
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            print("--- Histórico ---")
            print(f.read())
            print("-----------------")
    else:
        print("📭 Sem mensagens anteriores.")

def abrir_chat_sala(nome_sala: str):
    global usuario_logado, cliente_socket,sala_atual
    sala_atual = nome_sala
    pasta = f"chats/{usuario_logado}"
    caminho_arquivo = os.path.join(pasta, f"chat_grupo_{nome_sala}.txt")

    print(f"\n📂 Abrindo sala: {nome_sala}\n")

    exibir_historico(caminho_arquivo)

    # Monitorar novas mensagens em background
    parar_evento = threading.Event()
    t = threading.Thread(target=monitorar_historico, args=(caminho_arquivo, parar_evento), daemon=True)
    t.start()

    print(f"\nDigite mensagens para a sala {nome_sala}. Use '/voltar', '/expulsar <usuario>'.")
    while True:
        entrada = input(f"[Você → SALA {nome_sala}]: ").strip()
        if entrada.upper() == "/VOLTAR":
            parar_evento.set()
            t.join()
            sala_atual = None
            break
        elif entrada.upper() == "/SAIR":
            acao = "SAIR_SALA"
            enviar_json(cliente_socket, {
                    "CMD": acao,
                    "SALA": nome_sala
                })
            cache_salas[nome_sala] = {}
            sala_atual = None
            parar_evento.set()
            t.join()
            print("Você saiu da sala.")
            break
        elif entrada.startswith("/expulsar"):
            partes = entrada.split()
            if len(partes) == 2:
                acao = "EXPULSAR_USUARIO"
                usuario_alvo = partes[1]
                enviar_json(cliente_socket, {
                    "CMD": acao,
                    "SALA": nome_sala,
                    "ALVO": usuario_alvo,
                })
            else:
                print("Uso correto: /expulsar <usuario>")
        else:
            cache_sala_atual = cache_salas.get(nome_sala, {})
            for membro, chave in cache_sala_atual.items():

                if membro == usuario_logado:
                    continue
                payload = criptografar_mensagem(entrada, chave)
                msg = {
                    "CMD": "ENVIAR_MSG_SALA",
                    "DESTINATARIO": membro,
                    "PAYLOAD": payload,
                    "SALA": nome_sala
                }
                enviar_json(cliente_socket, msg)
            salvar_mensagem_grupo(nome_sala, usuario_logado, entrada)

def abrir_chat(usuario_chat: str):
    global usuario_logado, chaves_peers_cache, cliente_socket, chat_atual

    chat_atual = usuario_chat
    pasta = f"chats/{usuario_logado}"
    caminho_arquivo = os.path.join(pasta, f"chat_{usuario_chat}.txt")
    parar_evento = threading.Event()
    t = threading.Thread(target=monitorar_historico, args=(caminho_arquivo, parar_evento), daemon=True)
    t.start()

    print(f"\n📂 Abrindo conversa com {usuario_chat}...\n")

    exibir_historico(caminho_arquivo)

    # Chat interativo
    print(f"\nDigite mensagens para {usuario_chat}. Digite '/voltar' para voltar ao menu ou '/sair' para sair da sala.")
    while True:
        time.sleep(0.5)
        entrada = input(f"[Você → {usuario_chat}]: ").strip()
        if entrada.upper() == "/VOLTAR":
            print("💨 Saindo do chat.")
            parar_evento.set()
            t.join()
            chat_atual = None
            break
        if not entrada:
            continue
        if usuario_chat not in chaves_peers_cache:
            print("⚠️ Chave pública do destinatário não encontrada. Use LISTAR_PEERS.")
            continue
        payload = criptografar_mensagem(entrada, chaves_peers_cache[usuario_chat])
        if payload:
            msg = {
                "CMD": "ENVIAR_MSG",
                "DESTINATARIO": usuario_chat,
                "PAYLOAD": payload
            }
            enviar_json(cliente_socket, msg)
            salvar_mensagem_direta(usuario_chat, usuario_logado, entrada)

def criar_pasta_chat_usuario(usuario):
    pasta = f"chats/{usuario}"
    os.makedirs(pasta, exist_ok=True)
    
def salvar_mensagem_direta(destinatario: str, remetente: str, mensagem: str):
    global usuario_logado

    outro_usuario = destinatario if remetente == usuario_logado else remetente

    nome_remetente = "Eu" if remetente == usuario_logado else remetente

    pasta = f"chats/{usuario_logado}"
    os.makedirs(pasta, exist_ok=True)

    arquivo = os.path.join(pasta, f"chat_{outro_usuario}.txt")

    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(arquivo, "a", encoding="utf-8") as f:
        f.write(f"[{agora}] {nome_remetente}: {mensagem}\n")

def salvar_mensagem_grupo(sala: str, remetente: str, mensagem: str):
    global usuario_logado

    nome_remetente = "Eu" if remetente == usuario_logado else remetente

    pasta = f"chats/{usuario_logado}"
    os.makedirs(pasta, exist_ok=True)

    arquivo = os.path.join(pasta, f"chat_grupo_{sala}.txt")

    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(arquivo, "a", encoding="utf-8") as f:
        f.write(f"[{agora}] {nome_remetente}: {mensagem}\n")
    
def ouvinte_servidor():
    global usuario_logado, chaves_peers_cache, chave_publica_servidor, chat_atual, sala_atual

    while True:
        if not cliente_socket:
            break

        resposta = receber_json(cliente_socket)
        if not resposta:
            print("\n[INFO] Desconectado do servidor. Pressione ENTER para sair.")
            break

        status = resposta.get("STATUS")
        remetente = resposta.get("REMETENTE")

        match status:
            case "CHAVE_PUBLICA":
                chave_publica_servidor = resposta.get("CHAVE_PUBLICA")
                print("[CLIENT] SUCESSO AO ATRIBUIR CHAVE PUBLICA DO SERVIDOR") if chave_publica_servidor != None else print("[CLIENT] ERRO AO ATRIBUIR CHAVE PUBLICA DO SERVIDOR")
            
            case "MSG_DIRETA":
                mensagem = descriptografar_mensagem(resposta["PAYLOAD"], chave_privada)
                if chat_atual != remetente:
                    print(f"[MENSAGEM RECEBIDA] {remetente}\n")
                salvar_mensagem_direta(usuario_logado, remetente, mensagem)

            case "MSG_SALA":
                sala = resposta["SALA"]
                mensagem = descriptografar_mensagem(resposta["PAYLOAD"], chave_privada)
                if sala != sala_atual:
                    print(f"[MENSAGEM RECEBIDA NA SALA] {sala}\n")

                salvar_mensagem_grupo(sala, remetente, mensagem)

            case "ATUALIZACAO_SALA":
                nome_sala = resposta["SALA"]
                cache_salas[nome_sala] = {
                    membro["usuario"]: membro["chave"]
                    for membro in resposta["MEMBROS"]
                }
                membros = list(cache_salas[nome_sala].keys())
                print(f"\n[INFO] Lista de membros da sala {nome_sala} foi atualizada: {membros}")

            case "USUARIO_EXPULSO":
                print(f'\n[INFO] O usuário {resposta["ALVO"]} foi expulso da sala.')
            case "EXPULSO":
                sala = resposta["SALA"]
                cache_salas[sala] = {}  # Limpa o cache da sala
                print(f'\n[INFO] {resposta.get("MENSAGEM", "Expulso da sala.")}.')
            case "ERRO":
                print(f'\n[ERRO] {resposta.get("MENSAGEM", "Erro desconhecido.")}')
            
            case "CADASTRO_REALIZADO":
                print("Cadastro Realizado.")

            case "LOGIN_REALIZADO":
                usuario_logado = resposta.get("NOME")
                print("[CLIENT] LOGIN REALIZADO")
                criar_pasta_chat_usuario(usuario_logado)

            case "OK" if "PEERS" in resposta:
                print("\n--- Peers Ativos ---")
                for peer in resposta["PEERS"]:
                    print(f"- {peer['usuario']}")
                    chaves_peers_cache[peer["usuario"]] = peer["chave"]
                print("--------------------")

            case "SALA_CRIADA" | "ENTROU_NA_SALA":
                criar_chat_grupo(resposta["SALA"])

            case "SAIU_DA_SALA":
                print("Você saiu da sala.")

            case _:
                print(f"\n[SERVIDOR/DESCONHECIDO]: {json.dumps(resposta)}")

def conectar_servidor():
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect(('localhost', 12001))
        return cliente
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao servidor: {e}")
        return None

def formatar_comando_login_cadastro(comando:str):
    nome = input("Nome de usuário: ").strip()
    senha = input("Senha: ").strip()
    senha_criptografada = criptografar_mensagem(senha, chave_publica_servidor)
    nome_criptogradado = criptografar_mensagem(nome, chave_publica_servidor)
    if comando == "LOGIN":
        return {"CMD":comando, "NOME": nome_criptogradado, "SENHA": senha_criptografada, "CHAVE_PUBLICA": chave_publica}
    return {"CMD":comando, "NOME": nome_criptogradado, "SENHA": senha_criptografada, "CHAVE_PUBLICA": chave_publica}

def formatar_comando_enviar_mensagem(partes):
    if len(partes) < 3: return None
    destinatario, texto = partes[1], " ".join(partes[2:])
    if destinatario not in chaves_peers_cache:
        print(f"Chave de {destinatario} não encontrada. Use LISTAR_PEERS.")
        return None
    payload_cifrado = criptografar_mensagem(texto, chaves_peers_cache[destinatario])
    if payload_cifrado:
        return destinatario, texto,{"DESTINATARIO": destinatario, "PAYLOAD": payload_cifrado, "CMD": "ENVIAR_MSG"}
    else:
        return None

def formatar_comando_deslogar(partes):
    global usuario_logado
    comando = partes[0].upper()
    if not usuario_logado: return None
    nome = usuario_logado
    usuario_logado = None
    return {"CMD": comando, "NOME": nome}
    
def formatar_comando_enviar_mensagem_sala(partes):
    if len(partes) < 3: return None
    destinatario, texto = partes[1], " ".join(partes[2:])
    if destinatario not in chaves_peers_cache:
        print(f"Chave de {destinatario} não encontrada. Use LISTAR_PEERS.")
        return None
    payload_cifrado = criptografar_mensagem(texto, chaves_peers_cache[destinatario])
    if payload_cifrado:
        return destinatario, texto,{"DESTINATARIO": destinatario, "PAYLOAD": payload_cifrado, "CMD": "ENVIAR_MSG_SALA"}
    else:
        return None

def formatar_comando_criar_sala(comando):
    nome_sala = input("Nome da sala: ").strip()
    senha_sala = input("Senha da sala: ").strip()
    senha_cript = criptografar_mensagem( senha_sala, chave_publica_servidor)
    cache_salas[nome_sala] = {}
    return {"CMD": comando, "SALA": nome_sala, "SENHA": senha_cript}

def formatar_comando_entrar_sala(comando):
    nome_sala = input("Nome da sala: ").strip()
    senha_sala = input("Senha da sala: ").strip()
    senha_cript = criptografar_mensagem(senha_sala, chave_publica_servidor)
    cache_salas[nome_sala] = {} 
    return {"CMD": comando, "SALA": nome_sala, "SENHA": senha_cript}

def listar_chats():
    global usuario_logado
    pasta = f"chats/{usuario_logado}"

    if os.path.exists(pasta):
        arquivos = os.listdir(pasta)
        if not arquivos:
            print("📁 Nenhum chat salvo ainda.")
        else:
            for nome in arquivos:
                print(f"- {nome}")
    else:
        print("📁 Nenhuma pasta salva ainda.")

def criar_chat_grupo(sala):
    global usuario_logado
    pasta = f"chats/{usuario_logado}"
    os.makedirs(pasta, exist_ok=True)
    arquivo = os.path.join(pasta, f"chat_grupo_{sala}.txt")
    
    if not os.path.exists(arquivo):
        with open(arquivo, "w", encoding="utf-8") as f:
            pass

def executar_comando(client_socket, cmd_completo):    
    global usuario_logado, membros_sala_cache

    partes = cmd_completo.split(" ")
    comando = partes[0].upper()
        
    match comando:
        case "LOGIN" | "CADASTRAR":
            comando_cifrado = formatar_comando_login_cadastro(comando)
            enviar_json(client_socket, comando_cifrado)
        case "DESLOGAR":
            comando = formatar_comando_deslogar(partes)
            enviar_json(client_socket, comando)
        case "LISTAR_PEERS":
            enviar_json(client_socket, {"CMD": comando})
        case "LISTAR_CHATS":
            listar_chats()
        case "MSG":
            destinatario, mensagem, comando_cifrado = formatar_comando_enviar_mensagem(partes)
            salvar_mensagem_direta(destinatario,usuario_logado, mensagem)
            enviar_json(client_socket, comando_cifrado)
        case "ABRIR_CHAT_SALA":
            if len(partes) < 2:
                print("Uso: ABRIR_CHAT_SALA <nome_da_sala>")
            else:
                abrir_chat_sala(partes[1])
        case "ABRIR_CHAT":
            if len(partes) < 2:
                print("Uso: ABRIR_CHAT <nome_do_usuario>")
            else:
                abrir_chat(partes[1])
        case "CRIAR_SALA":
            comando_sala = formatar_comando_criar_sala(comando)
            enviar_json(cliente_socket, comando_sala)
        case "ENTRAR_SALA":
            comando_sala = formatar_comando_entrar_sala(comando)
            enviar_json(cliente_socket, comando_sala)
        case _:
            print(f"Comando desconhecido: {comando}")
            
def main():
    global cliente_socket, usuario_logado, chave_privada, chave_publica
    # Gera o par de chaves real na inicialização
    chave_privada, chave_publica = gerar_par_chaves()

    cliente_socket = conectar_servidor()
    if not cliente_socket: return
    
    thread_ouvinte = threading.Thread(target=ouvinte_servidor, daemon=True)
    thread_ouvinte.start()

    while True:
        if not usuario_logado:
            print("\n--- Menu Principal ---")
            print("Comandos disponíveis:")
            print(" - LOGIN")
            print(" - CADASTRAR")
            print(" - SAIR\n")
        elif usuario_logado:
            print(f"\n--- Logado como: {usuario_logado} ---")
            print("Comandos disponíveis:")
            print(" - LISTAR_PEERS              → Ver usuários online")
            print(" - MSG <usuario> <texto>     → Enviar mensagem direta")
            print(" - LISTAR_CHATS              → Ver seus chats salvos")
            print(" - ABRIR_CHAT <usuario>      → Abrir chat direto com alguém")
            print(" - CRIAR_SALA                → Criar uma nova sala")
            print(" - ENTRAR_SALA               → Entrar em uma sala existente")
            print(" - ABRIR_CHAT_SALA <sala>    → Abrir chat de uma sala")
            print(" - DESLOGAR                  → Encerrar sua sessão")
            print(" - SAIR                      → Sair do sistema\n")
        try:
            comando_input = input("> ").strip()
        except KeyboardInterrupt:
            break
            
        if not comando_input: continue
        cmd_base = comando_input.split(" ")[0].upper()
        if cmd_base == "SAIR": break

        executar_comando(cliente_socket, comando_input)
        time.sleep(0.5)
    print("\nEncerrando conexão...")
    if usuario_logado:
        enviar_json(cliente_socket, {"CMD": "DESLOGAR", "NOME": usuario_logado})
    cliente_socket.close()

if __name__ == "__main__":
    main()
