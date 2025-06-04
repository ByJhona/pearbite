from threading import Thread
from socket import socket, AF_INET, SOCK_STREAM
import json
from gerenciadorUsuario import GerenciadorUsuarios
from util import receber_json, enviar_json


usuarios_ativos = {}

def configurar_servidor(porta) -> socket:
    servSocket = socket(AF_INET, SOCK_STREAM)
    servSocket.bind(('', porta))
    servSocket.listen(5)
    print(f"Servidor ouvindo na porta {porta}...")
    return servSocket

def deslogar_usuario(endereco):
    global usuarios_ativos
    for nome in list(usuarios_ativos):
        if usuarios_ativos[nome]['ENDERECO'] == endereco:
            del usuarios_ativos[nome]


def lidar_requisicao(conexao: socket, endereco, gerenciadorUsuarios:GerenciadorUsuarios):
    print(f"Conexão iniciada com {endereco}")
    global usuarios_ativos
    try:
        while True:
            json_recebido = receber_json(conexao)
            if not json_recebido:
                print("Cliente desconectou ou enviou algo inválido.")
                break

            operacao = json_recebido.get('CMD', '')

            match operacao:
                case 'LOGIN':
                    nome = json_recebido.get('NOME')
                    senha = json_recebido.get('SENHA')
                    sucesso = gerenciadorUsuarios.login(nome, senha)
                    if sucesso:
                        usuarios_ativos[nome] = {'ENDERECO': endereco, 'CONEXAO': conexao}
                    status = "LOGIN_REALIZADO" if sucesso else "LOGIN_FALHOU"
                    enviar_json(conexao, {"STATUS": status})
                case 'DESLOGAR':
                    nome = json_recebido.get('NOME')
                    if nome in usuarios_ativos:
                        del usuarios_ativos[nome]
                case 'CADASTRAR':
                    nome = json_recebido.get('NOME')
                    senha = json_recebido.get('SENHA')
                    sucesso = gerenciadorUsuarios.cadastrar(nome, senha)
                    status = "CADASTRO_REALIZADO" if sucesso else "CADASTRO_FALHOU"
                    enviar_json(conexao, {"STATUS": status})
                case 'LISTAR_PEERS':
                    lista = [{"usuario": nome, "ip": info["ENDERECO"]} for nome, info in usuarios_ativos.items()]
                    enviar_json(conexao, {"STATUS": "OK", "PEERS": lista})
                case _:
                    print(f"Comando desconhecido: {operacao}")
                    enviar_json(conexao, {"ERRO": "Comando inválido"})
    finally:
        deslogar_usuario(endereco)
        conexao.close()
        print(f"Conexão encerrada com {endereco}")

def iniciar_servidor():
    servidor = configurar_servidor(12000)
    gerenciadorUsuarios = GerenciadorUsuarios()

    while True:
        conexao, endereco = servidor.accept()
        thread = Thread(target=lidar_requisicao, args=(conexao, endereco, gerenciadorUsuarios))
        thread.start()

def main():
    iniciar_servidor()

if __name__ == '__main__':
    main()
