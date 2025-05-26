from threading import *
import time
from socket import *
import json



def configurar_servidor(porta) -> socket:
    servSocket = socket(AF_INET, SOCK_STREAM)
    servSocket.bind(('', porta))
    servSocket.listen(5)
    print(f"Servidor ouvindo na porta {porta}...")
    return servSocket


def receber_json(conexao:socket):
    dados = conexao.recv(2048)
    return json.loads(dados.decode())

def enviar_json(conexao:socket, obj):
    conexao.sendall(json.dumps(obj).encode())

def lidar_requisicao(conexao: socket, endereco):
    while True:
        json_recebido = receber_json(conexao)

        if json_recebido['CMD'] == 'LOGIN':
            print(json_recebido['USUARIO'])
            print(json_recebido['SENHA'])



        if not json_recebido:
            break

    conexao.close()

def iniciar_servidor():
    servidor = configurar_servidor(12000)

    while True:
        conexao, endereco = servidor.accept()
        thread = Thread(target=lidar_requisicao, args=(conexao,endereco))
        thread.start()

def main():
    iniciar_servidor()


if __name__ == '__main__':
    main()