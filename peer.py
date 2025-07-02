import socket
import json
import threading
import base64
import time
from util import criptografar_senha
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

def gerar_par_chaves():
    chave_privada = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    chave_publica = chave_privada.public_key()
    pem_chave_publica = chave_publica.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    print("[INFO] Par de chaves RSA real gerado (2048 bits).")
    return chave_privada, pem_chave_publica.decode('utf-8')

def criptografar_mensagem(mensagem: str, pem_chave_publica_str: str):
    try:
        chave_publica = serialization.load_pem_public_key(
            pem_chave_publica_str.encode('utf-8')
        )
        ciphertext = chave_publica.encrypt(
            mensagem.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(ciphertext).decode('utf-8')
    except Exception as e:
        print(f"[ERRO DE CRIPTOGRAFIA] {e}")
        return None

def descriptografar_mensagem(payload_b64: str, chave_privada):
    try:
        ciphertext = base64.b64decode(payload_b64)
        plaintext = chave_privada.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return plaintext.decode('utf-8')
    except Exception as e:
        print(f"\n[ERRO DE DECIFRAGEM] A mensagem pode estar corrompida ou não era para você. {e}")
        return "[Mensagem não pôde ser decifrada]"

# Variáveis globais
usuario_logado = None
sala_atual = None
cliente_socket = None
membros_sala_cache = {}
chave_privada = None
chave_publica = None
chaves_peers_cache = {}
mensagens_pendentes = []
aguardando_resposta = False

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
    global usuario_logado, aguardando_resposta, sala_atual, membros_sala_cache, chaves_peers_cache
    
    while True:
        if not cliente_socket:
            break

        resposta = receber_json(cliente_socket)
        if not resposta:
            mensagens_pendentes.append("[INFO] Desconectado do servidor.")
            break

        tipo_msg = resposta.get("TIPO")
        status_msg = resposta.get("STATUS")

        if tipo_msg == "MSG_DIRETA":
            payload_decifrado = descriptografar_mensagem(resposta['PAYLOAD'], chave_privada)
            mensagens_pendentes.append(f"[MSG de {resposta['REMETENTE']}]: {payload_decifrado}")

        elif tipo_msg == "MSG_SALA":
            payload_decifrado = descriptografar_mensagem(resposta['PAYLOAD'], chave_privada)
            mensagens_pendentes.append(f"[SALA {resposta['SALA']} | {resposta['REMETENTE']}]: {payload_decifrado}")

        elif tipo_msg == "ATUALIZACAO_SALA":
            membros_sala_cache.clear()
            for membro in resposta["MEMBROS"]:
                membros_sala_cache[membro['usuario']] = membro['chave']
            mensagens_pendentes.append(f"[INFO] Lista de membros da sala atualizada. Sala: {list(membros_sala_cache.keys())}")

        elif status_msg == "EXPULSO":
            sala_atual = None
            membros_sala_cache.clear()
            mensagens_pendentes.append(f"[INFO] Você foi expulso da sala: {resposta.get('SALA')}")
            aguardando_resposta = False

        elif status_msg:
            if status_msg == "LOGIN_REALIZADO":
                usuario_logado = resposta.get("NOME")
                mensagens_pendentes.append(f"[SERVIDOR]: Login realizado com sucesso!")
                aguardando_resposta = False

            elif status_msg == "LOGIN_FALHOU":
                mensagens_pendentes.append(f"[SERVIDOR]: Falha no login!")
                aguardando_resposta = False

            elif status_msg == "CADASTRO_REALIZADO":
                mensagens_pendentes.append(f"[SERVIDOR]: Cadastro realizado com sucesso!")
                aguardando_resposta = False

            elif status_msg == "OK" and "PEERS" in resposta:
                if resposta["PEERS"]:
                    lista_peers = "\n".join(f"- {peer['usuario']}" for peer in resposta["PEERS"])
                else:
                    lista_peers = "(Nenhum peer ativo)"
                mensagens_pendentes.append(f"--- Peers Ativos ---\n{lista_peers}\n--------------------")
                for peer in resposta["PEERS"]:
                    chaves_peers_cache[peer['usuario']] = peer['chave']

            elif status_msg == "OK" and "SALAS" in resposta:
                if resposta["SALAS"]:
                    lista_salas = "\n".join(
                        f"- {sala['nome']} (Moderador: {sala['moderador']}, Membros: {sala['membros']})"
                        for sala in resposta["SALAS"]
                    )
                else:
                    lista_salas = "(Nenhuma Sala)"
                mensagens_pendentes.append(f"--- Lista de Salas ---\n{lista_salas}\n--------------------")

            elif status_msg in ["SALA_CRIADA", "ENTROU_NA_SALA"]:
                sala_atual = resposta.get("SALA")
                mensagens_pendentes.append(f"[SERVIDOR]: {resposta.get('MENSAGEM', 'Operação realizada com sucesso')}")

            elif status_msg == "SAIU_DA_SALA":
                mensagens_pendentes.append(f"[SERVIDOR]: Você saiu da sala: {sala_atual}")
                sala_atual = None

            elif status_msg == "SALA_REMOVIDA":
                mensagens_pendentes.append(f"[SERVIDOR]: Sala removida com sucesso.")
                sala_atual = None

        else:
            mensagens_pendentes.append(f"[SERVIDOR/DESCONHECIDO]: {json.dumps(resposta)}")

def conectar_servidor():
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect(('localhost', 12001))
        return cliente
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao servidor: {e}")
        return None

def print_separador():
    print("===========================================================================")

def print_menu():
    if not usuario_logado:
        print("\n--- Menu Principal ---")
        print("Comandos: LOGIN, CADASTRAR, SAIR")
    elif usuario_logado and not sala_atual:
        print(f"\n--- Logado como: {usuario_logado} ---")
        print("Comandos: LISTAR_PEERS, LISTAR_SALAS, MSG <user> <msg>, CRIAR_SALA, ENTRAR_SALA, REMOVER_SALA, DESLOGAR, SAIR")
    elif usuario_logado and sala_atual:
        print(f"\n--- Logado como: {usuario_logado} | Sala: {sala_atual} ---")
        print("Comandos: SALA_MSG <msg>, EXPULSAR_USUARIO, SAIR_SALA, LISTAR_PEERS, LISTAR_SALAS, MSG <user> <msg>, DESLOGAR, SAIR")
    print_separador()

def montar_mensagem(comando_input: str):
    global aguardando_resposta, usuario_logado, sala_atual, membros_sala_cache, chaves_peers_cache
    
    partes = comando_input.split(" ")
    cmd = partes[0].upper()
    msg = {"CMD": cmd}

    if cmd in ["LOGIN", "CADASTRAR"]:
        aguardando_resposta = True
        msg["NOME"] = input("Nome de usuário: ").strip()
        msg["SENHA"] = criptografar_senha(input("Senha: ").strip())
        if cmd == "LOGIN":
            msg["CHAVE_PUBLICA"] = chave_publica
        print_separador()
        return msg

    elif cmd == "DESLOGAR":
        if not usuario_logado:
            return None
        msg["NOME"] = usuario_logado
        usuario_logado = None
        sala_atual = None
        membros_sala_cache.clear()
        return msg

    elif cmd in ["LISTAR_PEERS", "LISTAR_SALAS"]:
        return msg

    elif cmd == "MSG":
        if len(partes) < 3:
            print("Uso: MSG <destinatario> <mensagem>")
            return None
        destinatario = partes[1]
        texto = " ".join(partes[2:])
        if destinatario not in chaves_peers_cache:
            print(f"Destinatário '{destinatario}' não encontrado ou sem chave pública.")
            return None
        payload_cifrado = criptografar_mensagem(texto, chaves_peers_cache[destinatario])
        if not payload_cifrado:
            return None
        return {
            "CMD": "ENVIAR_MSG",
            "DESTINATARIO": destinatario,
            "PAYLOAD": payload_cifrado
        }

    elif cmd in ["CRIAR_SALA", "ENTRAR_SALA"]:
        nome_sala = input("Nome da sala: ").strip()
        if not nome_sala:
            print("O nome da sala não pode estar vazio.")
            return None
        msg["SALA"] = nome_sala
        if cmd == "ENTRAR_SALA":
            msg["SENHA"] = criptografar_senha(input("Senha da sala: ").strip())
        membros_sala_cache.clear()
        aguardando_resposta = True
        return msg

    elif cmd == "REMOVER_SALA":
        if not sala_atual:
            print("Você não está em nenhuma sala.")
            return None
        msg["SALA"] = sala_atual
        msg["SENHA"] = criptografar_senha(input("Senha do moderador: ").strip())
        aguardando_resposta = True
        return msg

    elif cmd == "SAIR_SALA":
        if not sala_atual:
            return None
        msg["SALA"] = sala_atual
        membros_sala_cache.clear()
        aguardando_resposta = True
        return msg

    elif cmd == "SALA_MSG":
        if not sala_atual:
            print("Você não está em nenhuma sala.")
            return None
        texto = " ".join(partes[1:])
        if not texto:
            print("A mensagem não pode ser vazia.")
            return None
        for usuario, chave_publica_membro in membros_sala_cache.items():
            payload_cifrado = criptografar_mensagem(texto, chave_publica_membro)
            if payload_cifrado:
                enviar_json(cliente_socket, {
                    "CMD": "ENVIAR_MSG",
                    "DESTINATARIO": usuario,
                    "PAYLOAD": payload_cifrado
                })
        return None

    elif cmd == "EXPULSAR_USUARIO":
        if not sala_atual:
            print("Você não está em nenhuma sala.")
            return None
        msg["SALA"] = sala_atual
        msg["USUARIO"] = input("Usuário a expulsar: ").strip()
        msg["SENHA"] = criptografar_senha(input("Senha do moderador: ").strip())
        aguardando_resposta = True
        return msg

    else:
        print("Comando inválido.")
        return None

def main():
    global cliente_socket, chave_privada, chave_publica, aguardando_resposta
    
    chave_privada, chave_publica = gerar_par_chaves()
    cliente_socket = conectar_servidor()
    if not cliente_socket:
        return

    thread_ouvinte = threading.Thread(target=ouvinte_servidor, daemon=True)
    thread_ouvinte.start()

    try:
        while True:
            # Mostrar mensagens pendentes
            while mensagens_pendentes:
                print(mensagens_pendentes.pop(0))
                print_separador()
            
            # Mostrar menu se não estiver aguardando resposta
            if not aguardando_resposta:
                print_menu()
                try:
                    comando_input = input("> ").strip()
                    print_separador()
                except KeyboardInterrupt:
                    print("\nInterrupção detectada. Saindo...")
                    break
                
                if not comando_input:
                    continue
                    
                if comando_input.upper() == "SAIR":
                    break
                    
                msg = montar_mensagem(comando_input)
                if msg:
                    enviar_json(cliente_socket, msg)
            
            # Pequena pausa para evitar uso excessivo da CPU
            time.sleep(0.1)
            
    finally:
        if usuario_logado:
            enviar_json(cliente_socket, {"CMD": "DESLOGAR", "NOME": usuario_logado})
        cliente_socket.close()
        print("Conexão encerrada.")

if __name__ == "__main__":
    main()