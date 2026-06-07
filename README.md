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
- `GET  /v1/images/{image_id}`
- `GET  /v1/audio/{audio_id}`
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

O backend mantém um histórico curto em memória por `session_id` enquanto o
processo estiver rodando. Esse histórico é enviado ao provider de conversa para
dar continuidade à sessão. Se a criança pedir algo como `tente novamente`, o
backend reexecuta a última solicitação sem sucesso da sessão, priorizando
geração de imagem que terminou com `image=null`; se não houver falha, reexecuta
a última solicitação normal.

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

## Geração de imagem: fake ou OpenRouter

A geração de imagem fica desligada por padrão. O backend só tenta gerar imagem
quando a resposta de conversa vier com `intent=generate_image` e
`image_prompt` preenchido.

Configuração local segura com fake:

```env
IMAGE_GENERATION_ENABLED=true
IMAGE_PROVIDER=fake
IMAGE_STORAGE_PATH=/app/data/images
PUBLIC_IMAGE_BASE_URL=http://localhost:8080/v1/images
IMAGE_OUTPUT_FORMAT=png
IMAGE_DEFAULT_ASPECT_RATIO=1:1
IMAGE_DEFAULT_SIZE=800x800
```

Configuração com OpenRouter:

```env
IMAGE_GENERATION_ENABLED=true
IMAGE_PROVIDER=openrouter
OPENROUTER_API_KEY=<sua-chave>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_IMAGE_MODEL=google/gemini-3.1-flash-image-preview
OPENROUTER_HTTP_REFERER=http://localhost:8080
OPENROUTER_APP_TITLE=Robotic Assist Child
IMAGE_TIMEOUT_SECONDS=60
IMAGE_MAX_RETRIES=1
IMAGE_FALLBACK_TO_FAKE=true
```

O modelo de imagem usado é `google/gemini-3.1-flash-image-preview`
(Nano Banana 2). O prompt de imagem é validado pelo `SafetyGuard` antes de
chamar o provider. Se a geração falhar e `IMAGE_FALLBACK_TO_FAKE=true`, o
servidor usa `FakeImageGenerationProvider`.

Para testar pelo celular apontando para o notebook, ajuste a URL pública das
imagens para o IP da máquina, por exemplo:

```env
PUBLIC_IMAGE_BASE_URL=http://192.168.0.155:8080/v1/images
OPENROUTER_HTTP_REFERER=http://192.168.0.155:8080
```

`IMAGE_DEFAULT_SIZE=800x800` é enviado no prompt de geração. Para Gemini, o
request também usa `image_config.aspect_ratio=1:1` e `image_config.image_size=1K`,
que é a resolução suportada mais próxima no OpenRouter.

Não commite `.env` nem chaves OpenRouter.

Teste:

```bash
IMAGE_GENERATION_ENABLED=true \
IMAGE_PROVIDER=fake \
docker compose up --build

curl -X POST http://localhost:8080/v1/interactions/text \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_local",
    "client_type": "test",
    "input_text": "Cubinho, desenha um foguete azul indo para a lua.",
    "metadata": {
      "device_id": "local_test",
      "locale": "pt-BR"
    }
  }'
```

Quando houver imagem, a resposta inclui:

```json
{
  "image": {
    "image_id": "img_123",
    "image_url": "http://localhost:8080/v1/images/img_123",
    "content_type": "image/png",
    "provider": "fake",
    "model": "fake-image-placeholder",
    "created_at": "2026-06-07T20:00:00Z",
    "expires_at": null
  }
}
```

O arquivo fica temporariamente em `IMAGE_STORAGE_PATH` e é servido por
`GET /v1/images/{image_id}`. S3/CDN e múltiplas imagens ficam fora desta fase.
No Docker Compose local, `./data/images` é montado em `/app/data/images`.

## Áudio (TTS): fake ou ElevenLabs

A geração de áudio é **opcional** e **desligada por padrão**. O contrato textual
não muda: quando o áudio não é gerado, a resposta traz `"audio": null`. O áudio
só é sintetizado quando a requisição envia `"generate_audio": true` **e**
`TTS_ENABLED=true`. O texto enviado ao TTS é a resposta do assistente já
validada pelo `SafetyGuard`. O áudio é melhor-esforço: uma falha do ElevenLabs
nunca quebra a resposta textual (retorna `audio: null`).

Provider fake (sem chave, ideal para dev/testes — gera um WAV curto local):

```env
TTS_ENABLED=true
TTS_PROVIDER=fake
TTS_STORAGE_PATH=/app/data/audio
PUBLIC_AUDIO_BASE_URL=http://localhost:8080/v1/audio
```

Provider ElevenLabs (chamada HTTP real):

```env
TTS_ENABLED=true
TTS_PROVIDER=elevenlabs
TTS_OUTPUT_FORMAT=mp3_44100_128
ELEVENLABS_API_KEY=sk-...
ELEVENLABS_BASE_URL=https://api.elevenlabs.io
ELEVENLABS_VOICE_ID=<id-da-voz>
ELEVENLABS_TTS_MODEL=eleven_flash_v2_5
ELEVENLABS_TTS_TIMEOUT_SECONDS=30
ELEVENLABS_TTS_MAX_RETRIES=2
```

A chave de API e os headers (`xi-api-key`) nunca são logados, e nenhum áudio de
entrada é armazenado. Os testes automatizados nunca chamam a API real (usam
`httpx.MockTransport`).

### Como escolher `ELEVENLABS_VOICE_ID`

O `voice_id` identifica a voz no ElevenLabs. Para obtê-lo:

- No painel: **Voices** → selecione/adicione uma voz → copie o **Voice ID**.
- Via API: `GET https://api.elevenlabs.io/v1/voices` com o header
  `xi-api-key: <sua-chave>` e use o campo `voice_id` da voz desejada.

Para PT-BR, prefira modelos multilíngues (ex.: `eleven_flash_v2_5`, que é o
padrão e tem baixa latência). A requisição também aceita sobrescrever por
interação via `metadata.voice_id` e `metadata.tts_output_format`.

### Exemplo de requisição/resposta com áudio

```bash
curl -s http://localhost:8080/v1/interactions/text \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "session_demo",
    "client_type": "test",
    "input_text": "Oi Cubinho, tudo bem?",
    "generate_audio": true,
    "metadata": {"device_id": "rpi-001", "locale": "pt-BR"}
  }'
```

```json
{
  "interaction_id": "int_123",
  "assistant_text": "Oi! Tudo ótimo por aqui!",
  "audio": {
    "audio_id": "aud_123",
    "audio_url": "http://localhost:8080/v1/audio/aud_123",
    "content_type": "audio/mpeg",
    "duration_ms": null,
    "provider": "elevenlabs",
    "model": "eleven_flash_v2_5",
    "created_at": "2026-06-07T12:00:00Z",
    "expires_at": null
  }
}
```

O arquivo fica temporariamente em `TTS_STORAGE_PATH` e é servido por
`GET /v1/audio/{audio_id}`. S3/CDN ficam fora desta fase. No Docker Compose
local, `./data/audio` é montado em `/app/data/audio`.

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
