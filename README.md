# robotic-assist-child-server

Backend (FastAPI) do projeto Robotic Assist Child — o "cérebro" do Cubinho.
Clientes (mobile, Raspberry Pi) falam com este servidor através do API Gateway.

Este repositório contém atualmente o **primeiro vertical slice do MVP 0.1**:
health checks, carregamento/reload de prompts, interação de texto com resposta
infantil segura (provider fake) e SafetyGuard mínimo.

## Arquitetura

Clean / Hexagonal Architecture:

```
domain         entidades, enums, regras puras (sem framework)
application    ports (interfaces), use cases, services (prompt composer, safety)
infrastructure adapters (prompt loader, fake provider, telemetry, repos)
interfaces     HTTP /v1, WebSocket
config         settings + composition root (container)
shared         logging JSON, datetime, errors, ids
```

Providers externos (OpenRouter, ElevenLabs), Postgres/Mongo/Redis e memória
têm **ports preparados**, mas não são implementados neste slice.

## Endpoints (/v1)

- `GET  /v1/health/live`
- `GET  /v1/health/ready`
- `GET  /v1/health/startup`
- `GET  /v1/health`
- `GET  /v1/version`
- `GET  /v1/prompts`
- `GET  /v1/prompts/{prompt_id}`
- `POST /v1/prompts/reload`
- `POST /v1/interactions/text`
- `WS   /v1/ws/sessions/{session_id}`

## Prompts

Os prompts ficam no repositório irmão `robotic-assist-child-prompts` e são
carregados via `metadata/prompt_manifest.yaml`. O caminho é configurável:

```env
PROMPTS_REPOSITORY_PATH=../robotic-assist-child-prompts   # local
PROMPTS_REPOSITORY_PATH=/app/prompts                      # Docker (volume :ro)
```

## Rodar com Docker Compose (a partir deste repositório)

```bash
cp .env.example .env
docker compose up --build
```

Validação:

```bash
curl http://localhost:8080/v1/health/live
curl http://localhost:8080/v1/health/ready
curl http://localhost:8080/v1/prompts
curl -X POST http://localhost:8080/v1/prompts/reload
curl -X POST http://localhost:8080/v1/interactions/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Oi Cubinho!"}'
curl http://localhost:8080/gateway/health
```

Os clientes devem usar o gateway (`http://localhost:8080`). O servidor também
expõe `http://localhost:8000` para desenvolvimento.

## Rodar localmente (sem Docker)

```bash
python3.13 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export PROMPTS_REPOSITORY_PATH=../robotic-assist-child-prompts
uvicorn robotic_assist_child_server.main:app --app-dir src --port 8000
```

## Testes

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Os testes usam fixtures de prompts em `tests/fixtures/prompts` e não dependem
de OpenRouter ou ElevenLabs reais.
