# PearBite
PearBite - Sistema de Chat P2P Seguro

DESCRIÇÃO:
PearBite é um sistema de mensagens peer-to-peer (P2P) seguro com servidor centralizado para descoberta de pares, utilizando criptografia RSA para comunicação privada.

FUNCIONALIDADES PRINCIPAIS:
- Autenticação segura de usuários
- Criptografia de ponta-a-ponta com RSA 2048 bits
- Salas de chat privadas
- Mensagens diretas entre usuários
- Sistema de moderação em salas
- Persistência de dados de usuários e salas

TECNOLOGIAS UTILIZADAS:
- Python 3.8+
- Biblioteca Cryptography
- Sockets TCP
- JSON para serialização

COMO INSTALAR E EXECUTAR:

1. Instale as dependências:
pip install cryptography

2. Execute o servidor (tracker):
python tracker.py

3. Execute o cliente:
python peer.py

COMANDOS DISPONÍVEIS:

* Antes do login:
LOGIN      - Autenticar no sistema
CADASTRAR  - Criar nova conta
SAIR       - Encerrar aplicação

* Após login:
LISTAR_PEERS   - Ver usuários disponíveis
LISTAR_SALAS   - Listar salas de chat
MSG <user> <msg> - Enviar mensagem privada
CRIAR_SALA     - Criar nova sala
ENTRAR_SALA    - Entrar em sala existente
REMOVER_SALA   - Remover uma sala (moderador)
DESLOGAR       - Sair da conta

* Dentro de uma sala:
SALA_MSG <msg>  - Enviar mensagem para a sala
EXPULSAR_USUARIO - Remover usuário (moderador)
SAIR_SALA       - Deixar a sala atual

ARQUITETURA DO SISTEMA:
O sistema consiste em:
1. Servidor Tracker (tracker.py) - Mantém registro dos usuários e salas
2. Clientes Peer (peer.py) - Conectam-se ao tracker e entre si
3. Gerenciadores (gerenciadorUsuario.py) - Lógica de usuários e salas
4. Utilitários (util.py) - Funções auxiliares

SEGURANÇA:
- Senhas armazenadas como hash SHA-256
- Chaves RSA de 2048 bits
- Cada mensagem é criptografada especificamente para o destinatário
- Verificação de integridade com hashes

ESTRUTURA DE ARQUIVOS:
pearbite/
├── tracker.py        # Servidor central
├── peer.py           # Cliente P2P
├── gerenciadorUsuario.py # Gerenciamento
├── usuario.py        # Classes Usuario/Sala
├── util.py           # Funções auxiliares
└── README.txt        # Este arquivo

LICENÇA:
MIT License - Consulte o arquivo LICENSE para detalhes.

CONTATO:
Para suporte ou contribuições, entre em contato com o desenvolvedor.