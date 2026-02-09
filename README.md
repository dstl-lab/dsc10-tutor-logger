# DSC 10 Tutor Logger

Logging API and PostgreSQL database for the DSC 10 AI Tutor. Deployed on the [Nautilus](https://nationalresearchplatform.org/nautilus/) Kubernetes cluster.

## Architecture

- **API**: FastAPI service that writes event logs to Postgres (`POST /events`, `GET /health`)
- **Database**: PostgreSQL 14 managed by the [Zalando Postgres Operator](https://github.com/zalando/postgres-operator), with PgBouncer connection pooling
- **CI/CD**: GitHub pushes mirror to GitLab, which builds and pushes the Docker image via Kaniko

```
GitHub (main) ──mirror──> GitLab CI ──kaniko──> GitLab Container Registry
                                                        │
Nautilus cluster (namespace: dsc-10-llm)                │
┌───────────────────────────────────────────────────────┐│
│  Ingress ──> Service ──> API Deployment ──────────────┘│
│                              │                         │
│                          PgBouncer ──> PostgreSQL       │
└───────────────────────────────────────────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `api/` | FastAPI application (source, Dockerfile, dependencies) |
| `api/dump_to_parquet.py` | Script to dump the events table to a Parquet file |
| `api/.env.example` | Template for database connection env vars |
| `schema.sql` | Database schema (events table + indexes) |
| `dev.yml` | Kubernetes manifest for **dev** (1 Postgres instance, 2 Gi storage, 1 API replica) |
| `prod.yml` | Kubernetes manifest for **prod** (2 Postgres instances, 20 Gi storage, 2 API replicas) |
| `.gitlab-ci.yml` | CI pipeline that builds and pushes the API image |
| `.github/workflows/mirror-to-gitlab.yml` | GitHub Action that mirrors pushes to GitLab |

## API

### `POST /events`

Log an event.

```bash
curl -X POST https://dsc10-tutor-logging-api-dev.nrp-nautilus.io/events \
  -H 'Content-Type: application/json' \
  -d '{"event_type": "query", "user_email": "user@ucsd.edu", "payload": {"question": "..."}}'
```

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_type` | string | yes | Event category |
| `user_email` | string | no | User identifier |
| `payload` | object | no | Arbitrary JSON data (default `{}`) |

**Response** (`201`):

```json
{"id": 1, "created_at": "2026-02-09T01:19:19.280176+00:00"}
```

### `GET /health`

Returns `{"status": "ok"}` if the API and database are reachable.

## Deploying

```bash
# Dev
kubectl apply -n dsc-10-llm -f dev.yml

# Prod
kubectl apply -n dsc-10-llm -f prod.yml

# Apply the database schema
kubectl run -i --rm schema-apply --image=postgres:14 --restart=Never -n dsc-10-llm -- \
  psql "postgresql://dsc10_tutor:<password>@dsc10-tutor-logs-dev:5432/dsc10_tutor_logs" \
  -f- < schema.sql
```

## Dumping the database

The `api/dump_to_parquet.py` script exports the entire events table to a Parquet file. It reads connection details from `api/.env` (copy `api/.env.example` and fill in `DB_PASSWORD`).

```bash
# Port-forward the database (run in a separate terminal)
kubectl port-forward svc/dsc10-tutor-logs-dev-pooler 5432:5432 -n dsc-10-llm

# Run the dump (override DB_HOST since you're connecting via port-forward)
cd api
DB_HOST=localhost uv run python dump_to_parquet.py            # writes events.parquet
DB_HOST=localhost uv run python dump_to_parquet.py out.parquet # custom filename
```

## Logging from a TypeScript frontend

### Setup

Define the API base URL for each environment:

```typescript
const LOG_API =
  process.env.NODE_ENV === "production"
    ? "https://dsc10-tutor-logging-api.nrp-nautilus.io"
    : "https://dsc10-tutor-logging-api-dev.nrp-nautilus.io";
```

### Logging an event

```typescript
interface LogEvent {
  event_type: string;
  user_email?: string;
  payload?: Record<string, unknown>;
}

async function logEvent(event: LogEvent): Promise<void> {
  try {
    const res = await fetch(`${LOG_API}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
    if (!res.ok) {
      console.error("Failed to log event:", res.status, await res.text());
    }
  } catch (err) {
    // Fire-and-forget — don't let logging errors break the app
    console.error("Failed to log event:", err);
  }
}
```

### Example usage

```typescript
// Log a tutor query
await logEvent({
  event_type: "tutor_query",
  user_email: "student@ucsd.edu",
  payload: {
    question: "How do I filter a DataFrame?",
    assignment: "hw3",
  },
});

// Log a UI interaction (no email needed)
logEvent({
  event_type: "button_click",
  payload: { button: "show_hint", problem: 4 },
});
```

### Fire-and-forget

For UI interactions where you don't want to `await` the network call, just call `logEvent(...)` without `await`. The function already catches errors internally so an unhandled promise rejection won't occur.

### CORS

The API currently has no CORS restrictions. If you hit CORS errors in the browser, the API will need a CORS middleware added (e.g. FastAPI's `CORSMiddleware`).

## Useful commands

```bash
# Check cluster status
kubectl get postgresql,pods,svc,ingress -n dsc-10-llm

# Get the dev database password
kubectl get secret dsc10-tutor.dsc10-tutor-logs-dev.credentials.postgresql.acid.zalan.do \
  -n dsc-10-llm -o 'jsonpath={.data.password}' | base64 -d

# View API logs
kubectl logs -l app=dsc10-tutor-logging-api-dev -n dsc-10-llm

# View Postgres logs
kubectl logs dsc10-tutor-logs-dev-0 -n dsc-10-llm

# Connect to the database via psql (from within the cluster)
kubectl run -i --tty --rm debug --image=postgres:14 --restart=Never -n dsc-10-llm -- \
  psql "postgresql://dsc10_tutor:<password>@dsc10-tutor-logs-dev-pooler:5432/dsc10_tutor_logs"
```

## Endpoints

| Environment | API URL | DB Service (internal) |
|---|---|---|
| Dev | `https://dsc10-tutor-logging-api-dev.nrp-nautilus.io` | `dsc10-tutor-logs-dev-pooler.dsc-10-llm.svc.cluster.local:5432` |
| Prod | `https://dsc10-tutor-logging-api.nrp-nautilus.io` | `dsc10-tutor-logs-prod-pooler.dsc-10-llm.svc.cluster.local:5432` |
