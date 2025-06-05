import hashlib
from socket import socket
import json


def criptografar_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def gerar_hash(dados: dict) -> str:
    dados_sem_hash = {k: v for k, v in dados.items() if k != "HASH"}
    json_str = json.dumps(dados_sem_hash, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()


def enviar_json(conexao: socket, obj: dict):
    try:
        obj_com_hash = obj.copy()
        obj_com_hash["HASH"] = gerar_hash(obj)
        conexao.sendall(json.dumps(obj_com_hash).encode())
    except Exception as ex:
        print(f"Erro ao enviar JSON: {ex}")


def receber_json(conexao: socket) -> dict | None:
    try:
        dados = conexao.recv(2048)
        if not dados:
            return None
        obj = json.loads(dados.decode())

        if "HASH" not in obj:
            print("Mensagem sem hash (modo compatibilidade).")
            return obj  # <<< Retorna mesmo sem hash

        hash_recebido = obj["HASH"]
        obj_sem_hash = {k: v for k, v in obj.items() if k != "HASH"}
        hash_calculado = gerar_hash(obj_sem_hash)

        if hash_recebido != hash_calculado:
            print("Hash inválido. Mensagem corrompida ou alterada.")
            return None

        return obj_sem_hash
    except Exception as ex:
        print(f"Erro ao receber JSON: {ex}")
        return None
