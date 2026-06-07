# robotic-assist-child-server

Backend (FastAPI) do projeto Robotic Assist Child — o "cérebro" do Cubinho.
Clientes (mobile, Raspberry Pi) falam com este servidor através do API Gateway.

Este repositório contém atualmente o **vertical slice do MVP**:
health checks, carregamento/reload de prompts, interação de texto com resposta
infantil segura, memória mínima por usuário e provider de conversa configurável
(`fake` ou `openrouter`).

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

Providers externos ficam atrás de ports. OpenRouter já possui adapter real com
fallback seguro para o provider fake. ElevenLabs permanece fora deste slice.

## Endpoints (/v1)

- `GET  /v1/health/live`
- `GET  /v1/health/ready`
- `GET  /v1/health/startup`
- `GET  /v1/health`
- `GET  /v1/version`
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET  /v1/auth/me`
- `GET  /v1/prompts`
- `GET  /v1/prompts/{prompt_id}`
- `POST /v1/prompts/reload`
- `POST /v1/interactions/text`
- `GET  /v1/memories`
- `POST /v1/memories`
- `WS   /v1/ws/sessions/{session_id}`

## Autenticação

Autenticação simples com JWT (access token) para preparar múltiplos usuários.
Senhas são armazenadas com hash Argon2; os usuários ficam na tabela `users`
(PostgreSQL no Docker, SQLite por padrão fora dele).

```bash
# Registrar (retorna access_token + dados do usuário)
curl -X POST http://localhost:8080/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "pai_ana", "password": "s3cret!"}'

# Login
curl -X POST http://localhost:8080/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "pai_ana", "password": "s3cret!"}'

# Usuário atual
curl http://localhost:8080/v1/auth/me \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

`POST /v1/interactions/text` aceita autenticação **opcional**:

- com `Authorization: Bearer <token>` válido → `user_id` vem do token;
- sem token → interação anônima (comportamento MVP preservado);
- com `DEV_AUTH_DISABLED=true` → não exige token e usa `user_id=dev_user`.

Variáveis relevantes: `JWT_SECRET`, `JWT_ALGORITHM`,
`JWT_ACCESS_TOKEN_EXPIRES_MINUTES`, `DATABASE_URL` / `POSTGRES_DSN`,
`DEV_AUTH_DISABLED`. Refresh token fica para fases futuras.

## Memória por usuário

Memória mínima por usuário, armazenada no MongoDB (coleção `user_memories`).
Quando `MONGODB_URI` não está definido, um repositório em memória é usado, então
o MVP e os testes rodam sem MongoDB. Os endpoints exigem autenticação
(`get_current_user`); com `DEV_AUTH_DISABLED=true` usam `dev_user`.

Sem embeddings, sem busca vetorial e sem LLM de extração (tudo adiado).

Extração baseada em regra (pt-BR, no fluxo de `/v1/interactions/text`): se o
texto contiver `eu gosto de X`, `gosto de X` ou `meu favorito é X`, uma memória
do tipo `interest` é criada (`Gosta de X.`). Antes de gerar a resposta, as
memórias do `user_id` são recuperadas e injetadas pelo `PromptComposer`. As
operações de memória são best-effort: uma falha no backend nunca quebra a
resposta da criança.

```bash
# Criar memória manualmente
curl -X POST http://localhost:8080/v1/memories \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"content": "Gosta de dinossauros.", "memory_type": "interest"}'

# Listar memórias do usuário atual
curl http://localhost:8080/v1/memories \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

Variáveis relevantes: `MONGODB_URI`, `MONGODB_DATABASE`.

## Conversação: fake ou OpenRouter

O provider padrão é fake, para o backend rodar localmente sem API key:

```env
CONVERSATION_PROVIDER=fake
```

Para usar OpenRouter:

```env
CONVERSATION_PROVIDER=openrouter
OPENROUTER_API_KEY=<sua-chave>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=openai/gpt-5.4-nano
OPENROUTER_CHAT_MODEL_FALLBACK=openai/gpt-5.4-mini
OPENROUTER_HTTP_REFERER=http://localhost:8080
OPENROUTER_APP_TITLE=Robotic Assist Child
OPENROUTER_FALLBACK_TO_FAKE=true
OPENROUTER_MAX_RETRIES=2
CONVERSATION_TEMPERATURE=0.4
CONVERSATION_MAX_TOKENS=700
CONVERSATION_TIMEOUT_SECONDS=30
```

Não commite `.env` nem qualquer chave de API. O `.env.example` deve conter
somente nomes de variáveis e valores locais não secretos.

O endpoint de interação mantém `response_text` para compatibilidade e também
retorna o contrato estruturado:

```json
{
  "assistant_text": "resposta curta em português brasileiro",
  "expression": "idle|happy|thinking|listening|speaking|surprised|confused|error",
  "intent": "chat|generate_image|activity|story|fallback",
  "image_prompt": null
}
```

O modelo padrão é `OPENROUTER_CHAT_MODEL`. Para solicitar o modelo alternativo
em uma chamada específica, envie `metadata.response_detail=elaborated`.

Teste com fake:

```bash
CONVERSATION_PROVIDER=fake docker compose up --build

curl -X POST http://localhost:8080/v1/interactions/text \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_local",
    "client_type": "test",
    "input_text": "Oi Cubinho!",
    "metadata": {
      "device_id": "local_test",
      "locale": "pt-BR"
    }
  }'
```

Teste com OpenRouter:

```bash
CONVERSATION_PROVIDER=openrouter \
OPENROUTER_API_KEY=<sua-chave> \
docker compose up --build

curl -X POST http://localhost:8080/v1/interactions/text \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_local",
    "client_type": "test",
    "input_text": "Cubinho, me conta uma história curta sobre um dinossauro.",
    "metadata": {
      "device_id": "local_test",
      "locale": "pt-BR"
    }
  }'
```

Se OpenRouter falhar, expirar, retornar erro transitório ou estiver sem API key,
o servidor usa `FakeConversationProvider` quando
`OPENROUTER_FALLBACK_TO_FAKE=true`.

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
  -d '{"input_text": "Oi Cubinho!", "client_type": "test"}'
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

Os testes usam fixtures de prompts em `tests/fixtures/prompts`, mock HTTP para
OpenRouter e não dependem de OpenRouter ou ElevenLabs reais.
