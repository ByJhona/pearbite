import socket
import json
import sys
import threading
import base64 # Importado para codificar o ciphertext para envio em JSON
from util import criptografar_senha
import os
from datetime import datetime
import time


# --- SEÇÃO DE CRIPTOGRAFIA REAL ---
# A biblioteca 'cryptography' é usada para as operações.
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

# --- Variáveis de Estado Globais ---
usuario_logado = None
cliente_socket = None
cache_salas = {}

# As variáveis de chave agora armazenarão a chave real
chave_privada = None
chave_publica = None
chaves_peers_cache = {}


def gerar_par_chaves():
    """
    Gera um par de chaves RSA (privada e pública).
    A chave privada é mantida como um objeto e a pública é serializada para envio.
    """
    # Gera a chave privada
    chave_privada = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    # Gera a chave pública correspondente
    chave_publica = chave_privada.public_key()
    
    # Serializa a chave pública para o formato PEM para que possa ser enviada como texto
    pem_chave_publica = chave_publica.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    print("[INFO] Par de chaves RSA real gerado (2048 bits).")
    # Retorna o objeto da chave privada e a string PEM da chave pública
    return chave_privada, pem_chave_publica.decode('utf-8')

def criptografar_mensagem(mensagem: str, pem_chave_publica_str: str):
    """
    Criptografa uma mensagem usando a chave pública (em formato PEM) de um destinatário.
    """
    try:
        # Carrega a chave pública a partir da string PEM recebida
        chave_publica = serialization.load_pem_public_key(
            pem_chave_publica_str.encode('utf-8')
        )
        
        # Criptografa a mensagem (convertida para bytes)
        ciphertext = chave_publica.encrypt(
            mensagem.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        # Codifica o resultado em Base64 para transporte seguro dentro de um JSON
        return base64.b64encode(ciphertext).decode('utf-8')
    except Exception as e:
        print(f"[ERRO DE CRIPTOGRAFIA] {e}")
        return None

def descriptografar_mensagem(payload_b64: str, chave_privada):
    """
    Descriptografa um payload (em Base64) usando a chave privada do próprio usuário.
    """
    try:
        # Decodifica o Base64 para obter o ciphertext original em bytes
        ciphertext = base64.b64decode(payload_b64)
        
        # Descriptografa o ciphertext usando a chave privada
        plaintext = chave_privada.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        # Retorna a mensagem original como string
        return plaintext.decode('utf-8')
    except Exception as e:
        print(f"\n[ERRO DE DECIFRAGEM] A mensagem pode estar corrompida ou não era para você. {e}")
        return "[Mensagem não pôde ser decifrada]"

# --- FIM DA SEÇÃO DE CRIPTOGRAFIA ---

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

def abrir_chat_sala(nome_sala: str):
    global usuario_logado, cliente_socket

    pasta = f"chats/{usuario_logado}"
    arquivo = os.path.join(pasta, f"chat_grupo_{nome_sala}.txt")

    print(f"\n📂 Abrindo sala: {nome_sala}\n")

    if os.path.exists(arquivo):
        with open(arquivo, "r", encoding="utf-8") as f:
            print("--- Histórico ---")
            print(f.read())
            print("-----------------")
    else:
        print("Sem mensagens anteriores na sala.")

    # Monitorar novas mensagens em background
    parar_evento = threading.Event()
    t = threading.Thread(target=monitorar_historico, args=(arquivo, parar_evento), daemon=True)
    t.start()

    print(f"\nDigite mensagens para a sala {nome_sala}. Use '/voltar' para voltar.")
    while True:
        time.sleep(0.5)
        entrada = input(f"[Você → SALA {nome_sala}]: ").strip()
        if entrada.upper() == "/VOLTAR":
            parar_evento.set()
            t.join()
            break
        elif entrada.upper() == "/SAIR":
            acao = "SAIR_SALA"
            enviar_json(cliente_socket, {
                    "CMD": acao,
                    "SALA": nome_sala
                })
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
    global usuario_logado, chaves_peers_cache, cliente_socket

    pasta = f"chats/{usuario_logado}"
    arquivo = os.path.join(pasta, f"chat_{usuario_chat}.txt")
    parar_evento = threading.Event()
    t = threading.Thread(target=monitorar_historico, args=(arquivo, parar_evento), daemon=True)
    t.start()

    print(f"\n📂 Abrindo conversa com {usuario_chat}...\n")

    if os.path.exists(arquivo):
        with open(arquivo, "r", encoding="utf-8") as f:
            historico = f.read()
            print("--- Histórico ---")
            print(historico)
            print("-----------------")
    else:
        print("Nenhum histórico salvo com esse usuário ainda.")

    # Chat interativo
    print(f"\nDigite mensagens para {usuario_chat}. Digite '/voltar' para voltar ao menu.")
    while True:
        time.sleep(0.5)
        entrada = input(f"[Você → {usuario_chat}]: ").strip()
        if entrada.upper() == "/VOLTAR":
            print("💨 Saindo do chat.")
            parar_evento.set()
            t.join()
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

def enviar_json(sock, dados):
    try:
        sock.sendall(json.dumps(dados).encode())
    except Exception as e:
        print(f"[ERRO AO ENVIAR] {e}")

def receber_json(sock):
    try:
        dados = sock.recv(2048)
        return json.loads(dados.decode()) if dados else None
    except Exception:
        return None

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
    global usuario_logado, chaves_peers_cache

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
            case "MSG_DIRETA":
                mensagem = descriptografar_mensagem(resposta["PAYLOAD"], chave_privada)
                salvar_mensagem_direta(usuario_logado, remetente, mensagem)

            case "MSG_SALA":
                mensagem = descriptografar_mensagem(resposta["PAYLOAD"], chave_privada)
                salvar_mensagem_grupo(resposta["SALA"], remetente, mensagem)

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

def formatar_comando_login_cadastro(partes):
    comando = partes[0].upper()
    nome = input("Nome de usuário: ").strip()
    senha = input("Senha: ").strip()
    senha_criptografada = criptografar_senha(senha)
    if comando == "LOGIN":
        return {"CMD":comando, "NOME": nome, "SENHA": senha_criptografada, "CHAVE_PUBLICA": chave_publica}
    return {"CMD":comando, "NOME": nome, "SENHA": senha_criptografada}

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

def formatar_comando_criar_sala(partes):
    if len(partes) < 2: return None
    nome_sala = partes[1]
    cache_salas[nome_sala] = {} 
    return {"CMD": "CRIAR_SALA", "SALA": partes[1]}

def formatar_comando_entrar_sala(partes):
    if len(partes) < 2: return None
    nome_sala = partes[1]
    cache_salas[nome_sala] = {} 
    return {"CMD": "ENTRAR_SALA", "SALA": nome_sala}

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
            comando_cifrado = formatar_comando_login_cadastro(partes)
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
            abrir_chat_sala(partes[1])
        case "ABRIR_CHAT":
            if len(partes) < 2:
                print("Uso: ABRIR_CHAT <nome_do_usuario>")
            else:
                abrir_chat(partes[1])
        case "CRIAR_SALA":
            comando_sala = formatar_comando_criar_sala(partes)
            enviar_json(cliente_socket, comando_sala)
        case "ENTRAR_SALA":
            comando_sala = formatar_comando_entrar_sala(partes)
            enviar_json(cliente_socket, comando_sala)
            


def main():
    global cliente_socket, usuario_logado, chave_privada, chave_publica
    # Gera o par de chaves real na inicialização
    chave_privada, chave_publica = gerar_par_chaves()

    cliente_socket = conectar_servidor()
    if not cliente_socket: return
    
    thread_ouvinte = threading.Thread(target=ouvinte_servidor, daemon=True)
    thread_ouvinte.start()

    while True:
        time.sleep(0.2)
        if not usuario_logado:
            print("\n--- Menu Principal ---")
            print("Comandos disponíveis:")
            print(" - LOGIN")
            print(" - CADASTRAR")
            print(" - SAIR\n")
        elif usuario_logado:
            print(f"\n--- Logado como: {usuario_logado} ---")
            print("Comandos disponíveis:")
            print(" - LISTAR_PEERS           → Ver usuários online")
            print(" - LISTAR_CHATS           → Ver seus chats salvos")
            print(" - ABRIR_CHAT <usuario>   → Abrir chat direto com alguém")
            print(" - ABRIR_CHAT_SALA <sala> → Abrir chat de uma sala")
            print(" - MSG <usuario> <texto>  → Enviar mensagem direta")
            print(" - CRIAR_SALA <nome>      → Criar uma nova sala")
            print(" - ENTRAR_SALA <nome>     → Entrar em uma sala existente")
            print(" - DESLOGAR               → Encerrar sua sessão")
            print(" - SAIR                   → Sair do sistema\n")
        try:
            comando_input = input("> ").strip()
        except KeyboardInterrupt:
            break
            
        if not comando_input: continue
        cmd_base = comando_input.split(" ")[0].upper()
        if cmd_base == "SAIR": break

        executar_comando(cliente_socket, comando_input)

    print("\nEncerrando conexão...")
    if usuario_logado:
        enviar_json(cliente_socket, {"CMD": "DESLOGAR", "NOME": usuario_logado})
    cliente_socket.close()

if __name__ == "__main__":
    main()
