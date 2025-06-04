import hashlib
from socket import socket
import json


def receber_json(conexao: socket) -> dict | None:
    try:
        dados = conexao.recv(2048)
        if not dados:
            return None
        return json.loads(dados.decode())
    except Exception as ex:
        print(f"Erro ao receber JSON: {ex}")
        return None

def enviar_json(conexao: socket, obj):
    try:
        conexao.sendall(json.dumps(obj).encode())
    except Exception as ex:
        print(f"Erro ao enviar JSON: {ex}")

def criptografar_senha(senha:str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()
