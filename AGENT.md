# AGENT.md — Robotic Assist Child Server

## Repository purpose

This repository contains the backend server for the Robotic Assist Child project.

The server is the central orchestration layer for:

- authentication;
- users;
- devices;
- sessions;
- prompts;
- memory;
- interactions;
- safety rules;
- OpenRouter integration;
- ElevenLabs integration;
- observability;
- API versioning;
- WebSocket events;
- persistence.

Clients such as mobile apps and Raspberry Pi appliances must not contain business logic. They must call this backend through the API Gateway.

---

## Current project state

The project has four repositories:

- `robotic-assist-child-prompts`
- `robotic-assist-child-server`
- `robotic-assist-child-mobile`
- `robotic-assist-child-rpi`

Work must be done on the `develop` branch unless explicitly instructed otherwise.

---

## Mandatory stack

Use:

- Python 3.13+
- FastAPI
- Pydantic
- Uvicorn
- PostgreSQL
- MongoDB
- Redis
- SQLAlchemy or SQLModel
- Alembic
- OpenTelemetry
- Pytest
- Docker
- Docker Compose
- Nginx as initial API Gateway

All dependencies must use stable, pinned versions.

Do not use version ranges.

Correct:

```text
fastapi==x.y.z
uvicorn[standard]==x.y.z
sqlalchemy==x.y.z
```

Incorrect:

```text
fastapi
fastapi>=x.y.z
fastapi~=x.y.z
```

---

## Architecture

Use Clean Architecture / Hexagonal Architecture.

Required layers:

```text
domain
application
infrastructure
interfaces
config
shared
```

Rules:

- Domain must not depend on FastAPI.
- Domain must not depend on PostgreSQL, MongoDB or Redis.
- Domain must not depend on OpenRouter, ElevenLabs or AWS.
- Application layer must depend on ports/interfaces.
- Infrastructure layer implements adapters.
- HTTP and WebSocket controllers must not contain business logic.
- Prompt engineering must be centralized in a prompt composer service.
- External providers must be replaceable without changing use cases.

---

## Expected structure

```text
.
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── alembic.ini
├── alembic/
├── gateway/
│   └── nginx.conf
├── otel/
│   └── otel-collector-config.yaml
├── src/
│   └── robotic_assist_child_server/
│       ├── main.py
│       ├── config/
│       │   ├── settings.py
│       │   └── providers.py
│       ├── domain/
│       │   ├── entities/
│       │   ├── value_objects/
│       │   ├── enums/
│       │   └── events/
│       ├── application/
│       │   ├── ports/
│       │   ├── use_cases/
│       │   └── services/
│       ├── infrastructure/
│       │   ├── auth/
│       │   ├── database/
│       │   ├── mongodb/
│       │   ├── redis/
│       │   ├── openrouter/
│       │   ├── elevenlabs/
│       │   ├── telemetry/
│       │   ├── prompts/
│       │   └── repositories/
│       ├── interfaces/
│       │   ├── http/
│       │   │   └── v1/
│       │   └── websocket/
│       └── shared/
│           ├── logging/
│           ├── datetime.py
│           ├── errors.py
│           └── ids.py
└── tests/
```

---

## API versioning

All APIs must be versioned.

Initial version:

```text
/v1
```

Do not create unversioned endpoints except API Gateway internal health if needed.

Required initial endpoints:

```http
GET  /v1/health
GET  /v1/health/live
GET  /v1/health/ready
GET  /v1/health/startup
GET  /v1/version

POST /v1/auth/register
POST /v1/auth/login
POST /v1/auth/refresh
POST /v1/auth/logout
GET  /v1/auth/me

GET  /v1/prompts
GET  /v1/prompts/{prompt_id}
POST /v1/prompts/reload

POST /v1/interactions/text
GET  /v1/interactions/{interaction_id}

GET  /v1/memories
POST /v1/memories
PATCH /v1/memories/{memory_id}
DELETE /v1/memories/{memory_id}

WS   /v1/ws/sessions/{session_id}
```

All JSON fields must use `snake_case`.

All API dates must use RFC3339 UTC.

---

## Healthchecks

Implement Kubernetes-friendly healthchecks.

### Liveness

```http
GET /v1/health/live
```

Must not depend on external databases.

### Readiness

```http
GET /v1/health/ready
```

Must check:

- PostgreSQL;
- MongoDB;
- Redis;
- prompts loaded;
- minimum configuration loaded.

Return HTTP 503 if not ready.

### Startup

```http
GET /v1/health/startup
```

Must check:

- configuration loaded;
- migrations state;
- prompts loaded;
- async workers started;
- OpenTelemetry initialized.

Return HTTP 503 while startup is incomplete.

---

## Configuration

Configuration loading order:

1. AWS Secrets Manager.
2. AWS Systems Manager Parameter Store.
3. Environment variables.
4. `.env` fallback.

In Phase 1, implement:

```text
EnvironmentConfigProvider
DotEnvConfigProvider
CompositeConfigProvider
```

Prepare interfaces/adapters for:

```text
AwsSecretsManagerConfigProvider
AwsParameterStoreConfigProvider
```

Do not hardcode secrets.

Do not log secrets.

---

## Database policy

Use PostgreSQL as the main relational database.

Use MongoDB for user memory and contextual memory.

Use Redis for cache, queue, active sessions and future pub/sub.

### PostgreSQL entities

Minimum tables:

```text
users
devices
sessions
interactions
interaction_responses
user_settings
auth_tokens
audit_events
```

Roles:

```text
admin
parent
child
device
```

A parent may manage multiple child profiles.

A device may be linked to a child.

Every interaction must be linked to:

```text
user_id
session_id
client_type
device_id optional
```

### MongoDB collections

Minimum collections:

```text
user_memories
memory_events
conversation_summaries
model_context_snapshots
```

Memory fields:

```json
{
  "memory_id": "mem_123",
  "user_id": "usr_123",
  "session_id": "session_123",
  "memory_type": "interest",
  "content": "A criança gosta de dinossauros.",
  "confidence": 0.8,
  "source": "user_interaction",
  "created_at": "2026-06-07T20:00:00Z",
  "updated_at": "2026-06-07T20:00:00Z",
  "expires_at": null
}
```

Memory types:

```text
preference
routine
restriction
interest
interaction_summary
safety_note
parent_instruction
```

---

## Authentication and sessions

Implement initial authentication with:

- username or email;
- password hash;
- JWT access token;
- JWT refresh token.

Do not store plain text passwords.

Prefer Argon2 or bcrypt.

Required endpoints:

```http
POST /v1/auth/register
POST /v1/auth/login
POST /v1/auth/refresh
POST /v1/auth/logout
GET  /v1/auth/me
```

Interactions must support authenticated users or device tokens.

---

## Memory behavior

Before generating a model response:

1. Identify `user_id` and `session_id`.
2. Retrieve relevant user memories from MongoDB.
3. Retrieve user settings from PostgreSQL.
4. Compose final prompt.
5. Call conversation provider.
6. Validate response through safety guard.
7. Return response.
8. Persist interaction asynchronously.
9. Evaluate whether memories must be created, updated or expired.

Create these ports/interfaces:

```text
MemoryRepository
MemoryRetriever
MemoryUpdater
MemoryPolicy
```

Initial implementations:

```text
MongoMemoryRepository
SimpleMemoryRetriever
RuleBasedMemoryUpdater
```

Avoid storing unnecessary sensitive information.

---

## Prompt loading

Prompts are stored in the separate repository:

```text
robotic-assist-child-prompts
```

The server must load prompts from:

```env
PROMPTS_REPOSITORY_PATH=/app/prompts
```

Each loaded prompt must include:

```text
id
path
content
content_hash
loaded_at
```

Implement:

```http
GET  /v1/prompts
GET  /v1/prompts/{prompt_id}
POST /v1/prompts/reload
```

Reload must not require application restart.

---

## Providers

External providers must be behind interfaces.

### OpenRouter

Port:

```text
ConversationModelProvider
```

Implementations:

```text
FakeConversationProvider
OpenRouterConversationProvider
```

Phase 1 must include a working fake provider.

OpenRouter integration may be prepared but does not need to call the real API unless explicitly requested.

### ElevenLabs

Ports:

```text
SpeechToTextProvider
TextToSpeechProvider
```

Implementations:

```text
FakeSpeechToTextProvider
FakeTextToSpeechProvider
ElevenLabsSpeechToTextProvider
ElevenLabsTextToSpeechProvider
```

Phase 1 does not need real STT/TTS.

Do not store audio.

---

## Safety guard

Create:

```text
SafetyGuard
```

Methods:

```text
validate_input_text
validate_assistant_response
```

Rules:

- never request personal data from the child;
- never encourage secrets from parents;
- never respond with adult content;
- never provide dangerous instructions;
- redirect unsafe requests gently;
- keep answers short, calm and predictable.

---

## OpenTelemetry

Instrument from Phase 1:

- traces;
- metrics;
- logs.

Instrument:

- FastAPI;
- HTTP client;
- PostgreSQL;
- MongoDB;
- Redis;
- prompt loading;
- prompt reload;
- prompt composition;
- interaction handling;
- memory retrieval;
- memory update;
- async persistence;
- OpenRouter adapter;
- ElevenLabs adapter.

Recommended spans:

```text
prompt.load_all
prompt.reload
interaction.handle_text
memory.retrieve
memory.update
conversation.generate
safety.validate_input
safety.validate_response
repository.interaction.save
```

Logs must be JSON and OpenTelemetry-compatible.

Log fields, when available:

```text
timestamp
severity_text
severity_number
service_name
service_version
deployment_environment
trace_id
span_id
session_id
user_id
device_id
interaction_id
event_name
message
attributes
```

Never log:

- passwords;
- tokens;
- API keys;
- audio;
- sensitive child data.

---

## Docker and Compose

Create an efficient Dockerfile.

Requirements:

- `python:3.13-slim` or newer;
- non-root user;
- efficient caching;
- no build tools in final image unless required;
- `PYTHONDONTWRITEBYTECODE=1`;
- `PYTHONUNBUFFERED=1`;
- Docker healthcheck;
- compatible with `linux/amd64` and `linux/arm64`.

Compose must include:

```text
server
postgres
mongodb
redis
otel-collector
api-gateway
```

API Gateway should initially use Nginx.

The gateway must:

- proxy `/v1` to the server;
- support WebSocket;
- preserve tracing headers;
- preserve authorization headers;
- prepare CORS;
- expose `/gateway/health`.

Clients should call the gateway, not the server directly.

---

## Tests

Create tests for:

```text
health live
health ready
health startup
prompt loading
prompt reload
auth register
auth login
interaction text
memory repository
async persistence basic flow
```

Use pytest.

Tests must not depend on real OpenRouter or ElevenLabs.

---

## Code quality

Follow:

- clean code;
- small functions;
- explicit names;
- typed interfaces;
- dependency inversion;
- structured errors;
- testable use cases;
- no business logic in controllers;
- no provider-specific code in use cases.

---

## Change policy

Do not commit automatically.

Before finishing, report:

- files created;
- files modified;
- commands run;
- tests run;
- known limitations.

---

## Validation commands

Expected local validation:

```bash
docker compose up --build
```

```bash
curl http://localhost:8080/v1/health/live
curl http://localhost:8080/v1/health/ready
curl http://localhost:8080/v1/prompts
curl -X POST http://localhost:8080/v1/prompts/reload
```

Register/login:

```bash
curl -X POST http://localhost:8080/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "parent@example.com",
    "password": "change_me",
    "role": "parent"
  }'
```

```bash
curl -X POST http://localhost:8080/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "parent@example.com",
    "password": "change_me"
  }'
```

---

## Final reminder

Prioritize a strong foundation over advanced features.

Do not implement real STT, real TTS or real image generation unless explicitly requested.

Keep the architecture ready for:

- OpenRouter;
- ElevenLabs;
- image generation;
- mobile client;
- Raspberry Pi appliance;
- multiple users;
- memory per user;
- Kubernetes deployment;
- observability.
