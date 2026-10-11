# HomeLab Pulse

API e dashboard para acompanhar a saúde de serviços e containers de um homelab. O objetivo é centralizar disponibilidade, métricas e incidentes de aplicações como Jellyfin, Stirling PDF, Portainer e serviços da stack *arr.

> Status: etapa 6 concluída — dashboard autenticado com indicadores e gráficos Plotly.

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
cp .env.example .env
alembic upgrade head
uvicorn homelab_pulse.main:app --reload
```

Acesse:

- API: `http://localhost:8000/api/v1/health`
- Swagger: `http://localhost:8000/docs`
- Dashboard: `http://localhost:8050`

Resposta esperada do health check:

```json
{
  "application": "HomeLab Pulse",
  "environment": "development",
  "version": "0.6.0",
  "status": "UP",
  "timestamp": "2026-10-08T12:00:00Z"
}
```

## Executar com Docker

```bash
docker compose up --build
```

O Compose prepara a API, o dashboard, PostgreSQL, Redis, o worker Celery e o agendador Celery Beat. Os dados locais são mantidos em volumes Docker.

## Autenticação

Principais rotas:

- `POST /api/v1/auth/register`: cria uma conta comum.
- `POST /api/v1/auth/login`: retorna um token JWT.
- `GET /api/v1/users/me`: retorna o perfil autenticado.
- `GET /api/v1/users`: lista usuários, disponível apenas para administradores.

Exemplo de cadastro:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Usuário Teste","email":"usuario@example.com","password":"SenhaForte@2026"}'
```

Para criar o primeiro administrador localmente:

```bash
python -m homelab_pulse.cli create-admin \
  --name "Administrador" \
  --email "admin@example.com"
```

Com Docker, execute o mesmo comando dentro do serviço:

```bash
docker compose exec api python -m homelab_pulse.cli create-admin \
  --name "Administrador" \
  --email "admin@example.com"
```

A senha é solicitada sem aparecer no terminal. Contas criadas pela rota pública sempre recebem o perfil comum.

## Servidores e serviços

Após autenticar, cada usuário pode gerenciar apenas os próprios recursos:

- `POST/GET /api/v1/servers`: cria e lista servidores.
- `GET/PATCH/DELETE /api/v1/servers/{id}`: gerencia um servidor.
- `POST/GET /api/v1/servers/{id}/services`: cria e lista serviços do servidor.
- `GET/PATCH/DELETE /api/v1/services/{id}`: gerencia um serviço.

Os tipos disponíveis são `http`, `docker`, `jellyfin`, `portainer` e `arr`. Recursos de outro usuário retornam `404`, sem revelar se realmente existem.

Exemplo de serviço:

```json
{
  "name": "Jellyfin",
  "kind": "jellyfin",
  "target_url": "http://jellyfin:8096",
  "enabled": true
}
```

## Monitoramento HTTP

- `POST /api/v1/services/{id}/check`: executa uma verificação imediata.
- `GET /api/v1/services/{id}/checks`: retorna o histórico mais recente.

Cada verificação registra disponibilidade, código HTTP, latência e erro. O histórico também respeita o proprietário do serviço.

## Incidentes e execução agendada

O Celery Beat agenda a verificação de todos os serviços habilitados. O worker executa as sondagens usando o Redis como fila:

- a primeira resposta `DOWN` abre um incidente;
- novas falhas não duplicam um incidente ainda aberto;
- a primeira resposta `UP` seguinte resolve o incidente automaticamente.

Principais rotas:

- `GET /api/v1/incidents`: lista os incidentes do usuário; aceita `?status=open` ou `?status=resolved`.
- `GET /api/v1/services/{id}/incidents`: lista o histórico de incidentes de um serviço.

O intervalo padrão é de 60 segundos e pode ser alterado com `MONITOR_INTERVAL_SECONDS`.

## Dashboard

O dashboard Plotly Dash fica disponível em `http://localhost:8050`. Use a mesma conta criada na API. O token permanece apenas na sessão do navegador e todas as consultas são filtradas pelo usuário autenticado.

Indicadores disponíveis:

- quantidade de servidores e serviços;
- disponibilidade e latência média das últimas 24 horas;
- serviços online, offline ou ainda sem dados;
- incidentes atualmente abertos;
- gráficos de estado, disponibilidade por serviço e histórico de latência;
- tabela com o estado mais recente de cada serviço.

A rota `GET /api/v1/dashboard` fornece os dados agregados usados pela interface.

## Agente Docker

O agente coleta nomes, imagens e estados dos containers sem receber acesso de escrita. Defina um `AGENT_TOKEN` forte no arquivo `.env` e execute:

```bash
docker compose -f agent-compose.yaml up --build -d
```

O endpoint `GET /api/v1/containers` exige o token Bearer. A API Docker fica isolada atrás do `docker-socket-proxy`, configurado com `POST=0`, e nunca é publicada diretamente. Por padrão, o agente responde somente em `127.0.0.1:8001`.

Consulte [a documentação de segurança do agente](docs/docker-agent.md) antes de liberar acesso por VPN ou proxy reverso.

## Estrutura inicial

```text
src/homelab_pulse/
├── api/             # Rotas HTTP
├── models/          # Entidades persistidas pelo SQLAlchemy
├── schemas/         # Contratos de entrada e saída
├── monitoring/      # Sondagem HTTP e ciclo de incidentes
├── celery_app.py    # Fila e agendamento periódico
├── tasks.py         # Tarefas executadas pelo worker
├── dashboard.py     # Interface autenticada com Plotly Dash
├── database.py      # Sessões assíncronas de banco
├── security.py      # Hash de senha e tokens JWT
├── config.py        # Configuração por variáveis de ambiente
└── main.py          # Criação da aplicação FastAPI
alembic/              # Migrações do banco de dados
tests/               # Testes automatizados
docs/                # Decisões e diagramas de arquitetura
```

## Fluxo de branches

- `main`: versão estável.
- `develop`: integração das etapas concluídas.

Cada mudança é registrada em um commit específico na `develop`. As entregas concluídas seguem por pull request para a `main`.

## Roadmap

- [x] Etapa 1 — fundação FastAPI, testes, Docker, CI e documentação.
- [x] Etapa 2 — usuários, autenticação JWT e autorização por perfil.
- [x] Etapa 3 — cadastro de servidores e serviços com isolamento por usuário.
- [x] Etapa 4 — monitor HTTP e agente Docker somente leitura.
- [x] Etapa 5 — métricas, incidentes e tarefas com Celery/Redis.
- [x] Etapa 6 — dashboard com indicadores e gráficos Plotly.
- [ ] Etapa 7 — integrações com Jellyfin, Portainer e stack *arr.
- [ ] Etapa 8 — segurança, cobertura de testes, documentação e deploy.

Consulte [a arquitetura planejada](docs/arquitetura.md) para entender os componentes e as decisões de segurança.
