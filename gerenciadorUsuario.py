import hashlib
import json
from usuario import Usuario

class GerenciadorUsuarios:
    def __init__(self, caminho_arquivo='usuario.txt'):
        self.caminho_arquivo = caminho_arquivo
        try:
            open(caminho_arquivo, 'a').close()
        except IOError:
            pass

    def cadastrar(self, nome: str, senha: str) -> bool:
        if self.usuario_existe(nome):
            return False

        usuario = Usuario(nome, senha)
        with open(self.caminho_arquivo, 'a') as f:
            f.write(usuario.to_json() + '\n')
        return True

    def login(self, nome: str, senha: str) -> bool:
        with open(self.caminho_arquivo, 'r') as f:
            for linha in f:
                try:
                    usuario = Usuario.from_json(linha)
                    if usuario.nome == nome and usuario.verificar_senha(senha):
                        return True
                except json.JSONDecodeError:
                    continue
        return False

    def usuario_existe(self, nome: str) -> bool:
        try:
            with open(self.caminho_arquivo, 'r') as f:
                for linha in f:
                    try:
                        usuario = Usuario.from_json(linha)
                        if usuario.nome == nome:
                            return True
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            return False
        return False

    def obter_hash_senha(self, nome: str) -> str | None:
        with open(self.caminho_arquivo, 'r') as f:
            for linha in f:
                try:
                    usuario = Usuario.from_json(linha)
                    if usuario.nome == nome:
                        return usuario.senha_criptografada
                except json.JSONDecodeError:
                    continue
        return None

class Sala:
    def __init__(self, nome: str, moderador: str, senha_hash: str):
        self.nome = nome
        self.moderador = moderador
        self.senha_hash = senha_hash

    def to_json(self) -> str:
        return json.dumps({
            "NOME": self.nome,
            "MODERADOR": self.moderador,
            "SENHA": self.senha_hash
        })

    @staticmethod
    def from_json(json_str: str):
        dados = json.loads(json_str.strip())
        return Sala(dados["NOME"], dados["MODERADOR"], dados["SENHA"])

class GerenciadorSalas:
    def __init__(self, caminho_arquivo='salas.txt'):
        self.caminho_arquivo = caminho_arquivo
        try:
            open(caminho_arquivo, 'a').close()
        except IOError:
            pass

    def salvar_sala(self, sala: Sala):
        with open(self.caminho_arquivo, 'a') as f:
            f.write(sala.to_json() + '\n')

    def sala_existe(self, nome_sala: str) -> bool:
        try:
            with open(self.caminho_arquivo, 'r') as f:
                for linha in f:
                    try:
                        sala = Sala.from_json(linha)
                        if sala.nome == nome_sala:
                            return True
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            return False
        return False

    def validar_moderador(self, nome_sala: str, senha: str) -> bool:
        senha_hash = hashlib.sha256(senha.encode()).hexdigest()
        try:
            with open(self.caminho_arquivo, 'r') as f:
                for linha in f:
                    try:
                        sala = Sala.from_json(linha)
                        if sala.nome == nome_sala and sala.senha_hash == senha_hash:
                            return True
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            return False
        return False

    def remover_sala(self, nome_sala: str, senha: str) -> bool:
        if not self.validar_moderador(nome_sala, senha):
            return False

        salas_restantes = []
        try:
            with open(self.caminho_arquivo, 'r') as f:
                for linha in f:
                    try:
                        sala = Sala.from_json(linha)
                        if sala.nome != nome_sala:
                            salas_restantes.append(sala)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            return False

        with open(self.caminho_arquivo, 'w') as f:
            for sala in salas_restantes:
                f.write(sala.to_json() + '\n')
        return True

    def listar_salas(self):
        salas = []
        try:
            with open(self.caminho_arquivo, 'r') as f:
                for linha in f:
                    try:
                        sala = Sala.from_json(linha)
                        salas.append(sala)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            return salas
        return salas