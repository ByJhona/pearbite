import os
from usuario import Usuario
import bcrypt
import json


class GerenciadorUsuarios:
    def __init__(self, caminho_arquivo='usuario.txt'):
        self.caminho_arquivo = caminho_arquivo

    def cadastrar(self, nome: str, senha: str) -> bool:
        if self.usuario_existe(nome):
            return False

        senha_bytes = senha.encode('utf-8')
        senha_hash = bcrypt.hashpw(senha_bytes, bcrypt.gensalt()).decode('utf-8')

        usuario = Usuario(nome, senha_hash)
        with open(self.caminho_arquivo, 'a') as f:
            f.write(usuario.to_json() + '\n')
        return True

    def usuario_existe(self, nome: str) -> bool:
        if not os.path.exists(self.caminho_arquivo):
            return False
        
        with open(self.caminho_arquivo, 'r') as f:
            for linha in f:
                usuario = Usuario.from_json(linha)
                if usuario.nome == nome:
                    return True
        return False
    
    def login(self, nome: str, senha_digitada: str) -> bool:
        with open(self.caminho_arquivo, 'r') as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    dados = json.loads(linha)
                except json.JSONDecodeError as e:
                    print(f"[ERRO JSON] Linha inválida: {linha} - {e}")
                    continue
                if dados.get('NOME') == nome:
                    senha_hash = dados.get('SENHA', "")
                    if senha_hash and bcrypt.checkpw(senha_digitada.encode('utf-8'), senha_hash.encode('utf-8')):
                        return True
                    else:
                        return False  

        return False  # Usuário não encontrado
