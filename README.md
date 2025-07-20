# 🐍 PearBite Chat P2P

## 🎯 Objetivo
Criar um sistema de chat **ponto a ponto (P2P)** em rede local, que permita:
- Cadastro e login seguro de usuários.
- Troca de mensagens diretas e em salas, sempre **cifradas**.
- Armazenamento local do histórico de conversas.

---

## 🛠 Ferramentas e tecnologias
- **Python** (Sockets TCP, Threads)
- **RSA 2048 bits** (criptografia de mensagens)
- **bcrypt** (hash seguro de senhas)
- Estrutura JSON para comunicação entre servidor e clientes
- Armazenamento local de histórico em arquivos `.txt`

---

> 📦 Projeto dividido em:
> - `tracker.py`: servidor central que gerencia usuários, salas e chaves públicas.
> - `peer.py`: cliente que gera chaves, envia mensagens cifradas e salva histórico local.
> - Módulos auxiliares para criptografia e persistência.

