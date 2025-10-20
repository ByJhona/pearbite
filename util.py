from socket import socket
import json
import base64 
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
#########################################################################################################

def enviar_json(conexao: socket, obj: dict):
    try:
        conexao.sendall(json.dumps(obj).encode())
    except Exception as e:
        print(f"[ERRO AO ENVIAR] {e}")


def receber_json(sock:socket):
    try:
        dados = sock.recv(2048)
        return json.loads(dados.decode()) if dados else None
    except Exception:
        return None
