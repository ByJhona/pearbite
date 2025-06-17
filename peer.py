"""
import socket
import json
import threading
from util import criptografar_senha

# --- Variáveis de Estado Globais ---
# Usadas para que a thread ouvinte possa alterar o estado que a thread principal lê
usuario_logado = None
sala_atual = None
cliente_socket = None

# --- PLACEHOLDER DE CRIPTOGRAFIA ---
chave_privada = "CHAVE_PRIVADA_DE_EXEMPLO"
chave_publica = "CHAVE_PUBLICA_DE_EXEMPLO"
chaves_peers_cache = {}

def gerar_par_chaves_placeholder():
    print("[INFO] Par de chaves pública/privada gerado.")
    pass

def criptografar_placeholder(mensagem, chave_publica_dest):
    return f"{mensagem} [cifrado com {chave_publica_dest[:10]}...]"

def descriptografar_placeholder(payload, chave_privada_propria):
    if "[cifrado com" in payload:
        return payload.split(" [cifrado com")[0]
    return payload

# --- FIM DO PLACEHOLDER DE CRIPTOGRAFIA ---

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

def ouvinte_servidor():
    
    #ÚNICA thread responsável por ouvir TODAS as mensagens do servidor.
    #Ela processa tanto mensagens de chat quanto respostas de status.
    
    global usuario_logado, sala_atual, chaves_peers_cache

    while True:
        if not cliente_socket:
            break
        
        resposta = receber_json(cliente_socket)
        if not resposta:
            print("\n[INFO] Desconectado do servidor. Pressione ENTER para sair.")
            break

        # Verifica se é uma mensagem de chat ou uma resposta de status
        tipo_msg = resposta.get("TIPO")
        status_msg = resposta.get("STATUS")

        if tipo_msg == "MSG_DIRETA":
            payload_decifrado = descriptografar_placeholder(resposta['PAYLOAD'], chave_privada)
            print(f"\n[MSG de {resposta['REMETENTE']}]: {payload_decifrado}")
        elif tipo_msg == "MSG_SALA":
            payload_decifrado = descriptografar_placeholder(resposta['PAYLOAD'], chave_privada)
            print(f"\n[SALA {resposta['SALA']} | {resposta['REMETENTE']}]: {payload_decifrado}")
        elif status_msg:
            # Processa respostas de status diretamente aqui
            print(f"\n[SERVIDOR]: {json.dumps(resposta)}")
            if status_msg == "LOGIN_REALIZADO":
                usuario_logado = resposta.get("NOME")
            elif status_msg in ["LOGIN_FALHOU", "CADASTRO_FALHOU"]:
                # Nada a fazer, apenas informa o usuário
                pass
            elif status_msg == "OK" and "PEERS" in resposta:
                print("\n--- Peers Ativos ---")
                for peer in resposta["PEERS"]:
                    print(f"- {peer['usuario']}")
                    chaves_peers_cache[peer['usuario']] = peer['chave']
                print("--------------------")
            elif status_msg == "SALA_CRIADA" or status_msg == "ENTROU_NA_SALA":
                sala_atual = resposta.get("SALA")
            elif status_msg == "SAIU_DA_SALA":
                print(f"Você saiu da sala: {sala_atual}")
                sala_atual = None
            elif status_msg == "OK" and "SALAS" in resposta:
                salas_ativas = resposta["SALAS"]
                print("\n--- Salas Ativas ---")
                if not salas_ativas:
                    print("Nenhuma sala ativa no momento.")
                else:
                    for sala in salas_ativas:
                        print(f"- Sala: {sala['nome']} | Moderador: {sala['moderador']} | Membros: {sala['membros']}")
                print("--------------------")
        else:
            # Resposta desconhecida
             print(f"\n[SERVIDOR/DESCONHECIDO]: {json.dumps(resposta)}")


def conectar_servidor():
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect(('localhost', 12001))
        return cliente
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao servidor: {e}")
        return None

def montar_mensagem(cmd_completo: str):

    global usuario_logado, sala_atual


    partes = cmd_completo.split(" ")
    cmd = partes[0].upper()
    
    msg = {"CMD": cmd}

    # Lógica de montagem de mensagens (sem alterações significativas)
    if cmd == "LOGIN" or cmd == "CADASTRAR":
        msg["NOME"] = input("Nome de usuário: ").strip()
        senha = input("Senha: ").strip()
        msg["SENHA"] = criptografar_senha(senha)
        if cmd == "LOGIN":
            msg["CHAVE_PUBLICA"] = chave_publica
    elif cmd == "DESLOGAR":
        if not usuario_logado:
            print("Você não está logado.")
            return None
        msg["NOME"] = usuario_logado
        usuario_logado = None
        sala_atual = None
    elif cmd == "LISTAR_PEERS":
        pass
    elif cmd == "MSG":
        if len(partes) < 3: return None
        destinatario, texto = partes[1], " ".join(partes[2:])
        if destinatario not in chaves_peers_cache:
            print(f"Chave pública de {destinatario} não encontrada. Use LISTAR_PEERS.")
            return None
        payload_cifrado = criptografar_placeholder(texto, chaves_peers_cache[destinatario])
        msg.update({"DESTINATARIO": destinatario, "PAYLOAD": payload_cifrado, "CMD": "ENVIAR_MSG"})
    elif cmd in ["CRIAR_SALA", "ENTRAR_SALA"]:
        if len(partes) < 2: return None
        msg["SALA"] = partes[1]
    elif cmd == "SAIR_SALA":
        if not sala_atual: return None
        msg["SALA"] = sala_atual
    elif cmd == "SALA_MSG":
        if not sala_atual: return None
        if len(partes) < 2: return None
        texto = " ".join(partes[1:])
        payload_cifrado = criptografar_placeholder(texto, "CHAVE_DA_SALA_PLACEHOLDER")
        msg.update({"SALA": sala_atual, "PAYLOAD": payload_cifrado, "CMD": "ENVIAR_MSG_SALA"})
    elif cmd == "LISTAR_SALAS":
        pass
    else:
        print("Comando inválido.")
        return None

    return msg

def main():
    global cliente_socket, usuario_logado, sala_atual
    gerar_par_chaves_placeholder()

    cliente_socket = conectar_servidor()
    if not cliente_socket:
        return
    
    # Inicia a thread para ouvir o servidor
    thread_ouvinte = threading.Thread(target=ouvinte_servidor, daemon=True)
    thread_ouvinte.start()

    while True:
        # A interface é atualizada com base nas variáveis globais que a thread ouvinte modifica
        if not usuario_logado:
            print("\n--- Menu Principal ---\nComandos: LOGIN, CADASTRAR, SAIR")
        elif usuario_logado and not sala_atual:
            print(f"\n--- Logado: {usuario_logado} ---\nComandos: LISTAR_PEERS, LISTAR_SALAS, MSG <user>, CRIAR_SALA <nome>, ENTRAR_SALA <nome>, DESLOGAR, SAIR")
        elif usuario_logado and sala_atual:
            print(f"\n--- Logado: {usuario_logado} | Sala: {sala_atual} ---\nComandos: SALA_MSG <msg>, SAIR_SALA, LISTAR_PEERS, LISTAR_SALAS, MSG <user>, DESLOGAR, SAIR")

        try:
            comando_input = input("> ").strip()
        except KeyboardInterrupt: # Permite sair com Ctrl+C
            break
            
        if not comando_input:
            continue

        cmd_base = comando_input.split(" ")[0].upper()
        if cmd_base == "SAIR":
            break

        msg = montar_mensagem(comando_input)
        if msg:
            enviar_json(cliente_socket, msg)

    print("\nEncerrando conexão...")
    if usuario_logado: # Desloga antes de sair se a conexão ainda estiver ativa
        enviar_json(cliente_socket, {"CMD": "DESLOGAR", "NOME": usuario_logado})
    cliente_socket.close()

if __name__ == "__main__":
    main()
"""

import socket
import json
import threading
import base64 # Importado para codificar o ciphertext para envio em JSON
from util import criptografar_senha

# --- SEÇÃO DE CRIPTOGRAFIA REAL ---
# A biblioteca 'cryptography' é usada para as operações.
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

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


# --- Variáveis de Estado Globais ---
usuario_logado = None
sala_atual = None
cliente_socket = None
membros_sala_cache = {}

# As variáveis de chave agora armazenarão a chave real
chave_privada = None
chave_publica = None
chaves_peers_cache = {}


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

def ouvinte_servidor():
    global usuario_logado, sala_atual, chaves_peers_cache

    while True:
        if not cliente_socket: break
        
        resposta = receber_json(cliente_socket)
        if not resposta:
            print("\n[INFO] Desconectado do servidor. Pressione ENTER para sair.")
            break

        tipo_msg = resposta.get("TIPO")
        status_msg = resposta.get("STATUS")

        if tipo_msg == "MSG_DIRETA":
            # Usa a função de decifragem real
            payload_decifrado = descriptografar_mensagem(resposta['PAYLOAD'], chave_privada)
            print(f"\n[MSG de {resposta['REMETENTE']}]: {payload_decifrado}")
        elif tipo_msg == "MSG_SALA":
            # Usa a função de decifragem real
            payload_decifrado = descriptografar_mensagem(resposta['PAYLOAD'], chave_privada)
            print(f"\n[SALA {resposta['SALA']} | {resposta['REMETENTE']}]: {payload_decifrado}")
        elif tipo_msg == "ATUALIZACAO_SALA":
            membros_sala_cache.clear()
            for membro in resposta["MEMBROS"]:
                membros_sala_cache[membro['usuario']] = membro['chave']
            print(f"\n[INFO] Lista de membros da sala foi atualizada. Na sala com: {list(membros_sala_cache.keys())}")
        elif status_msg:
            print(f"\n[SERVIDOR]: {json.dumps(resposta)}")
            if status_msg == "LOGIN_REALIZADO":
                usuario_logado = resposta.get("NOME")
            elif status_msg == "OK" and "PEERS" in resposta:
                print("\n--- Peers Ativos ---")
                for peer in resposta["PEERS"]:
                    print(f"- {peer['usuario']}")
                    chaves_peers_cache[peer['usuario']] = peer['chave']
                print("--------------------")
            elif status_msg == "SALA_CRIADA" or status_msg == "ENTROU_NA_SALA":
                sala_atual = resposta.get("SALA")
            elif status_msg == "SAIU_DA_SALA":
                print(f"Você saiu da sala: {sala_atual}")
                sala_atual = None
        else:
             print(f"\n[SERVIDOR/DESCONHECIDO]: {json.dumps(resposta)}")


def conectar_servidor():
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect(('localhost', 12001))
        return cliente
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao servidor: {e}")
        return None

def montar_mensagem(cmd_completo: str):
    global usuario_logado, sala_atual, membros_sala_cache

    partes = cmd_completo.split(" ")
    cmd = partes[0].upper()
    
    msg = {"CMD": cmd}

    if cmd == "LOGIN" or cmd == "CADASTRAR":
        msg["NOME"] = input("Nome de usuário: ").strip()
        senha = input("Senha: ").strip()
        msg["SENHA"] = criptografar_senha(senha)
        if cmd == "LOGIN":
            msg["CHAVE_PUBLICA"] = chave_publica
    elif cmd == "DESLOGAR":
        if not usuario_logado: return None
        msg["NOME"] = usuario_logado
        usuario_logado = None
        sala_atual = None
        membros_sala_cache.clear()
    elif cmd in ["LISTAR_PEERS", "LISTAR_SALAS"]:
        pass
    elif cmd == "MSG":
        if len(partes) < 3: return None
        destinatario, texto = partes[1], " ".join(partes[2:])
        if destinatario not in chaves_peers_cache:
            print(f"Chave de {destinatario} não encontrada. Use LISTAR_PEERS.")
            return None
        payload_cifrado = criptografar_mensagem(texto, chaves_peers_cache[destinatario])
        if payload_cifrado:
            msg.update({"DESTINATARIO": destinatario, "PAYLOAD": payload_cifrado, "CMD": "ENVIAR_MSG"})
        else:
            return None
    elif cmd in ["CRIAR_SALA", "ENTRAR_SALA"]:
        if len(partes) < 2: return None
        membros_sala_cache.clear()
        msg["SALA"] = partes[1]
    elif cmd == "SAIR_SALA":
        if not sala_atual: return None
        msg["SALA"] = sala_atual
        membros_sala_cache.clear()
    elif cmd == "SALA_MSG":
        if not sala_atual:
            print("Você não está em nenhuma sala.")
            return None
        
        texto = " ".join(partes[1:])
        if not texto:
            print("A mensagem não pode ser vazia.")
            return None
        
        print(f"[Enviando para a sala: {list(membros_sala_cache.keys())}]")
        for usuario, chave_publica_membro in membros_sala_cache.items():
            payload_cifrado = criptografar_mensagem(texto, chave_publica_membro)
            if payload_cifrado:
                msg_individual = {"CMD": "ENVIAR_MSG", "DESTINATARIO": usuario, "PAYLOAD": payload_cifrado}
                enviar_json(cliente_socket, msg_individual)
        return None # Mensagens já foram enviadas
    else:
        print("Comando inválido.")
        return None

    return msg

def main():
    global cliente_socket, usuario_logado, sala_atual, chave_privada, chave_publica
    # Gera o par de chaves real na inicialização
    chave_privada, chave_publica = gerar_par_chaves()

    cliente_socket = conectar_servidor()
    if not cliente_socket: return
    
    thread_ouvinte = threading.Thread(target=ouvinte_servidor, daemon=True)
    thread_ouvinte.start()

    while True:
        if not usuario_logado:
            print("\n--- Menu Principal ---\nComandos: LOGIN, CADASTRAR, SAIR")
        elif usuario_logado and not sala_atual:
            print(f"\n--- Logado: {usuario_logado} ---\nComandos: LISTAR_PEERS, LISTAR_SALAS, MSG <user> <msg>, CRIAR_SALA <nome>, ENTRAR_SALA <nome>, DESLOGAR, SAIR")
        elif usuario_logado and sala_atual:
            print(f"\n--- Logado: {usuario_logado} | Sala: {sala_atual} ---\nComandos: SALA_MSG <msg>, SAIR_SALA, LISTAR_PEERS, LISTAR_SALAS, MSG <user> <msg>, DESLOGAR, SAIR")

        try:
            comando_input = input("> ").strip()
        except KeyboardInterrupt:
            break
            
        if not comando_input: continue
        cmd_base = comando_input.split(" ")[0].upper()
        if cmd_base == "SAIR": break

        msg = montar_mensagem(comando_input)
        if msg:
            enviar_json(cliente_socket, msg)

    print("\nEncerrando conexão...")
    if usuario_logado:
        enviar_json(cliente_socket, {"CMD": "DESLOGAR", "NOME": usuario_logado})
    cliente_socket.close()

if __name__ == "__main__":
    main()
