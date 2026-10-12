# Deploy

O projeto foi preparado para deploy por Blueprint no Render usando `render.yaml`.

## Antes de criar o Blueprint

1. Crie um banco PostgreSQL persistente, como um projeto gratuito no Neon.
2. Copie a connection string e mantenha `sslmode=require`.
3. No Render, abra **New > Blueprint** e selecione este repositório na branch `main`.
4. Informe a variável `DATABASE_URL` quando o Render solicitar.
5. Confirme os recursos somente depois de revisar os custos.

O sistema aceita a connection string padrão `postgresql://...` e seleciona automaticamente o driver assíncrono `psycopg`.

## Recursos definidos

- `homelab-pulse-api`: API pública gratuita com health check.
- `homelab-pulse-dashboard`: dashboard público gratuito.
- `homelab-pulse-redis`: fila Key Value gratuita, acessível somente pela rede privada.
- `homelab-pulse-worker`: worker Celery com Beat no plano `0.5c-512mb`.

O worker é um recurso pago porque o Render não oferece background workers gratuitos. Não clique em **Deploy Blueprint** sem revisar essa cobrança. Para uma demonstração sem custos, remova temporariamente o worker do Blueprint e execute verificações manualmente pela API.

## Limitação de rede

Um serviço hospedado no Render não alcança endereços privados da rede doméstica, como `192.168.x.x`, nomes locais ou containers sem exposição externa. Para monitorar o homelab real, a implantação recomendada é o Docker Compose dentro da própria rede, ou acesso por uma VPN privada. Não publique Jellyfin, Portainer, Docker Engine ou aplicações *arr diretamente na internet apenas para permitir o monitoramento.

## Validação após o deploy

1. Abra `/api/v1/health` na URL da API e confirme a versão e o estado `UP`.
2. Abra `/docs` e crie uma conta comum por `POST /api/v1/auth/register`.
3. Acesse a URL do dashboard com a mesma conta.
4. Cadastre somente um endpoint seguro e acessível a partir do Render.
5. Confirme nos logs do worker que a tarefa periódica foi executada.

Os segredos JWT e de criptografia são gerados pelo Render e não são salvos no repositório. A URL do banco é solicitada durante a criação do Blueprint.
