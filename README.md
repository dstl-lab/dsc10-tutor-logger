# DSC 10 Tutor Logger

Logging API and PostgreSQL database for the DSC 10 Tutor JupyterLab extension. The API is a FastAPI service that stores usage and interaction logs. The database is a PostgreSQL 14 cluster managed by the [Zalando Postgres Operator](https://github.com/zalando/postgres-operator) on the Nautilus cluster.

## Files

| File | Description |
|------|-------------|
| `api/` | FastAPI logging API (Dockerfile, source, dependencies) |
| `dev.yml` | Kubernetes manifest for the **development** environment (1 instance, 2 Gi storage) |
| `prod.yml` | Kubernetes manifest for the **production** environment (2 instances, 20 Gi storage) |
| `schema.sql` | Database schema |
| `.gitlab-ci.yml` | CI pipeline to build and push the API image to GitLab Container Registry |

## CI/CD

Pushes to `main` on GitHub are automatically mirrored to GitLab via GitHub Actions. The GitLab CI pipeline builds the API Docker image using Kaniko and pushes it to:

```
gitlab-registry.nrp-nautilus.io/samlau95/dsc10-tutor-logger/api:latest
```

## Cluster Details

- **Namespace**: `dsc-10-llm`
- **Dev cluster**: `dsc10-tutor-logs-dev`
- **Prod cluster**: `dsc10-tutor-logs-prod`
- **Database name**: `dsc10_tutor_logs`
- **Users**: `postgres` (admin), `dsc10_tutor` (superuser, createdb)
- **Connection pooling**: PgBouncer enabled on both environments

## Connecting to the Development Database

### 1. Get the password

```bash
kubectl get secret postgres.dsc10-tutor-logs-dev.credentials.postgresql.acid.zalan.do \
  -n dsc-10-llm \
  -o 'jsonpath={.data.password}' | base64 -d
```

### 2. Port-forward the service

```bash
kubectl port-forward svc/dsc10-tutor-logs-dev 5432:5432 -n dsc-10-llm
```

### 3. Connect with Python

```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="dsc10_tutor_logs",
    user="postgres",
    password="<password from step 1>",
)

cur = conn.cursor()
cur.execute("SELECT version();")
print(cur.fetchone())

cur.close()
conn.close()
```

> **Note**: If connecting from within the cluster (e.g. from another pod), use the internal service DNS instead of `localhost`:
> - Direct: `dsc10-tutor-logs-dev.dsc-10-llm.svc.cluster.local:5432`
> - Via PgBouncer: `dsc10-tutor-logs-dev-pooler.dsc-10-llm.svc.cluster.local:5432`
