from socket import *
import json

mensagem = {'CMD':'LOGIN', 'USUARIO':'jhonatan', 'SENHA': '123456'}
mensagemJson = json.dumps(mensagem)

serverName = 'localhost'
serverPort = 12000
clientSocket = socket(AF_INET, SOCK_STREAM)
clientSocket.connect((serverName,serverPort))
clientSocket.send(mensagemJson.encode())
modifiedSentence = clientSocket.recv(1024)
print ('From Server:', modifiedSentence.decode())
clientSocket.close()