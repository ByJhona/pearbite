import socket
import json

def enviar_json(sock, dados):
    try:
        sock.sendall(json.dumps(dados).encode())
    except Exception as e:
        print(f"[ERRO AO ENVIAR] {e}")

def receber_json(sock):
    try:
        dados = sock.recv(2048)
        return json.loads(dados.decode()) if dados else None
    except Exception as e:
        print(f"[ERRO AO RECEBER] {e}")
        return None

def conectar_servidor():
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect(('localhost', 12000))
        return cliente
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao servidor: {e}")
        return None

def montar_mensagem(cmd, usuario_logado):
    msg = {"CMD": cmd}

    if cmd in {"LOGIN", "CADASTRAR"}:
        msg["NOME"] = input("Nome de usuário: ").strip()
        msg["SENHA"] = input("Senha: ").strip()
    elif cmd == "DESLOGAR":
        if not usuario_logado:
            print("Você não está logado.")
            return None
        msg["NOME"] = usuario_logado
    elif cmd == "LISTAR_PEERS":
        # TODO: Fazer isso mais estruturado
        pass
    else:
        print("Comando inválido.")
        return None

    return msg

def processar_resposta(cmd, resposta, usuario_logado):
    if not resposta:
        print("Sem resposta do servidor ou resposta inválida.")
        return usuario_logado

    print("Resposta:", json.dumps(resposta, indent=2))

    if cmd == "LOGIN" and resposta.get("STATUS") == "LOGIN_REALIZADO":
        return resposta.get("NOME") or usuario_logado
    elif cmd == "DESLOGAR":
        return None

    return usuario_logado

def main():
    cliente = conectar_servidor()
    if not cliente:
        return

    with cliente:
        usuario_logado = None

        while True:
            cmd = input("\nComando (LOGIN, CADASTRAR, DESLOGAR, LISTAR_PEERS, SAIR): ").strip().upper()
            if cmd == "SAIR":
                break

            msg = montar_mensagem(cmd, usuario_logado)
            if not msg:
                continue

            enviar_json(cliente, msg)
            resposta = receber_json(cliente)
            usuario_logado = processar_resposta(cmd, resposta, usuario_logado)

        print("Encerrando conexão...")

if __name__ == "__main__":
    main()
