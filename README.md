# HomeLab Pulse

API e dashboard para acompanhar a saúde de serviços e containers de um homelab. O objetivo é centralizar disponibilidade, métricas e incidentes de aplicações como Jellyfin, Stirling PDF, Portainer e serviços da stack *arr.

> Status: etapa 1 concluída — fundação da API, testes, Docker e integração contínua.

## O que o projeto demonstrará

- Backend assíncrono com Python e FastAPI.
- Autenticação JWT e isolamento dos dados por usuário.
- Monitoramento HTTP e coleta segura de informações do Docker.
- Processamento agendado com Celery e Redis.
- Histórico no PostgreSQL e dashboard com Plotly Dash.
- Testes automatizados, Docker Compose e GitHub Actions.

## Stack

- Python 3.12, FastAPI e Pydantic.
- PostgreSQL e Redis.
- Celery para tarefas agendadas.
- Plotly Dash para gráficos e indicadores.
- Pytest, Ruff, Docker e GitHub Actions.

## Executar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn homelab_pulse.main:app --reload
```

Acesse:

- API: `http://localhost:8000/api/v1/health`
- Swagger: `http://localhost:8000/docs`

Resposta esperada do health check:

```json
{
  "application": "HomeLab Pulse",
  "environment": "development",
  "version": "0.1.0",
  "status": "UP",
  "timestamp": "2026-10-08T12:00:00Z"
}
```

## Executar com Docker

```bash
docker compose up --build
```

O Compose prepara a API, PostgreSQL e Redis. Os dados locais são mantidos em volumes Docker.

## Estrutura inicial

```text
src/homelab_pulse/
├── api/             # Rotas HTTP
├── config.py        # Configuração por variáveis de ambiente
└── main.py          # Criação da aplicação FastAPI
tests/               # Testes automatizados
docs/                # Decisões e diagramas de arquitetura
```

## Fluxo de branches

- `main`: versão estável.
- `develop`: integração das etapas concluídas.
- `codex/etapa-*`: desenvolvimento isolado de cada etapa.

Cada mudança é registrada em um commit específico. As entregas passam por pull request para `develop` e depois para `main`.

## Roadmap

- [x] Etapa 1 — fundação FastAPI, testes, Docker, CI e documentação.
- [ ] Etapa 2 — usuários, autenticação JWT e autorização por perfil.
- [ ] Etapa 3 — cadastro de servidores e serviços com isolamento por usuário.
- [ ] Etapa 4 — monitor HTTP e agente Docker somente leitura.
- [ ] Etapa 5 — métricas, incidentes e tarefas com Celery/Redis.
- [ ] Etapa 6 — dashboard com indicadores e gráficos Plotly.
- [ ] Etapa 7 — integrações com Jellyfin, Portainer e stack *arr.
- [ ] Etapa 8 — segurança, cobertura de testes, documentação e deploy.

Consulte [a arquitetura planejada](docs/arquitetura.md) para entender os componentes e as decisões de segurança.

