import hashlib
import json

class Usuario:
    def __init__(self, nome: str, senha: str):
        self.nome = nome
        self.senha_criptografada = self._hash_senha(senha)

    def _hash_senha(self, senha: str) -> str:
        return hashlib.sha256(senha.encode()).hexdigest()

    def verificar_senha(self, senha: str) -> bool:
        return self.senha_criptografada == self._hash_senha(senha)

    def to_json(self) -> str:
        return json.dumps({"NOME": self.nome, "SENHA": self.senha_criptografada})
    
    @staticmethod
    def from_json(json_str: str):
        dados = json.loads(json_str.strip())
        usuario = Usuario(dados["NOME"], "")
        usuario.senha_criptografada = dados["SENHA"]
        return usuario