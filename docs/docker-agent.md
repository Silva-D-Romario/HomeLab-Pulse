# Agente Docker seguro

O agente deve ser executado no servidor que hospeda os containers. Ele consulta o Docker por meio do `docker-socket-proxy`; a aplicação principal nunca monta o socket Docker.

## Configuração

1. Copie `.env.example` para `.env`.
2. Troque `AGENT_TOKEN` por um valor longo e aleatório.
3. Execute `docker compose -f agent-compose.yaml up --build -d`.
4. Verifique `http://127.0.0.1:8001/health`.
5. Consulte os containers enviando `Authorization: Bearer <token>`.

## Limites de segurança

- `POST=0` impede operações de criação, alteração e exclusão no Docker.
- Somente os grupos `CONTAINERS`, `INFO` e `PING` estão habilitados no proxy.
- O proxy pertence a uma rede Docker interna e não possui porta publicada.
- O agente publica apenas no endereço de loopback.
- Para outro computador acessar o agente, prefira VPN privada, como Tailscale ou WireGuard.
- Nunca publique o Docker Engine na porta `2375` da rede ou da internet.

O token autentica o cliente, mas não substitui TLS ou VPN quando o tráfego sai do próprio servidor.
