from usuario import Usuario

class GerenciadorUsuarios:
    def __init__(self, caminho_arquivo='usuario.txt'):
        self.caminho_arquivo = caminho_arquivo

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
                usuario = Usuario.from_json(linha)
                if usuario.nome == nome and usuario.verificar_senha(senha):
                    return True
        return False

    def usuario_existe(self, nome: str) -> bool:
        with open(self.caminho_arquivo, 'r') as f:
            for linha in f:
                usuario = Usuario.from_json(linha)
                if usuario.nome == nome:
                    return True
        return False
