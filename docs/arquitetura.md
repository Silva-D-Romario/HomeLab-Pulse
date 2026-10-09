# Arquitetura planejada

```mermaid
flowchart LR
    U[Usuário] --> D[Dashboard Plotly Dash]
    D --> A[API FastAPI]
    A --> P[(PostgreSQL)]
    A --> R[(Redis)]
    R --> C[Celery Worker]
    C --> H[Monitor HTTP]
    C --> G[Agente Docker somente leitura]
    H --> S[Serviços do homelab]
    G --> X[Containers Docker]
    C --> P
```

## Responsabilidades

- **FastAPI:** autenticação, regras de acesso, cadastro e consulta de recursos.
- **PostgreSQL:** usuários, servidores, serviços, métricas e incidentes.
- **Redis/Celery:** fila e execução periódica das verificações.
- **Monitor HTTP:** disponibilidade, latência e código de resposta.
- **Agente Docker:** coleta somente leitura do estado e do consumo dos containers.
- **Plotly Dash:** visualização dos indicadores obtidos pela API.

## Isolamento dos dados

Servidores, serviços, métricas e incidentes terão um proprietário. Todas as consultas autenticadas deverão aplicar o identificador do usuário, impedindo que uma conta leia ou altere recursos de outra.

## Autenticação e autorização

As senhas são armazenadas somente como hashes Argon2. Após o login, a API emite um JWT com validade configurável. Rotas privadas validam o token e carregam o usuário diretamente do banco. O cadastro público sempre cria contas comuns; ações administrativas exigem o perfil `admin`, criado por um comando executado no servidor.

## Segurança do Docker

O socket Docker não será exposto diretamente à aplicação web. A coleta usará um agente restrito ou um proxy de socket com apenas as operações de leitura necessárias. Tokens de integrações serão recebidos por variáveis de ambiente e nunca versionados.
