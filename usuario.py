import json

class Usuario:
    def __init__(self, nome: str, senha: str):
        self.nome = nome
        self.senha_criptografada = senha

    def to_json(self) -> str:
        return json.dumps({"NOME": self.nome, "SENHA": self.senha_criptografada})
    
    @staticmethod
    def from_json(json_str: str):
        dados = json.loads(json_str.strip())
        usuario = Usuario(dados["NOME"], "")
        usuario.senha_criptografada = dados["SENHA"]
        return usuario