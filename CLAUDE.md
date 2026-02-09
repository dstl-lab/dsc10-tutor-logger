# Logging DB

## Cluster Info

- **Namespace**: `dsc-10-llm`
- **Cluster**: `nautilus`
- **Operator**: Zalando Postgres Operator (`acid.zalan.do/v1`)
- **Dev cluster name**: `dsc10-tutor-logs-dev`
- **Prod cluster name**: `dsc10-tutor-logs-prod`
- **Database**: `dsc10_tutor_logs`
- **Users**: `postgres` (admin), `dsc10_tutor` (superuser, createdb)
- **PgBouncer**: enabled on both dev and prod (`enableConnectionPooler: true`)

## Common Commands

### Deploy / teardown

```bash
# Apply
kubectl apply -n dsc-10-llm -f dev.yml
kubectl apply -n dsc-10-llm -f prod.yml

# Delete (WARNING: PVC is deleted too — data is lost)
kubectl delete postgresql dsc10-tutor-logs-dev -n dsc-10-llm

# Check status
kubectl get postgresql -n dsc-10-llm
kubectl get pods -n dsc-10-llm
kubectl get pvc -n dsc-10-llm
```

### Get password

```bash
# Dev
kubectl get secret dsc10-tutor.dsc10-tutor-logs-dev.credentials.postgresql.acid.zalan.do -n dsc-10-llm -o 'jsonpath={.data.password}' | base64 -d

# Prod
kubectl get secret dsc10-tutor.dsc10-tutor-logs-prod.credentials.postgresql.acid.zalan.do -n dsc-10-llm -o 'jsonpath={.data.password}' | base64 -d
```

### Connect via psql

```bash
# Start a debug pod
kubectl run -i --tty --rm debug --image=postgres -- bash

# Connect directly to postgres
PGPASSWORD=<password> psql -h dsc10-tutor-logs-dev -U postgres -d dsc10_tutor_logs

# Connect via pgbouncer pooler
PGPASSWORD=<password> psql -h dsc10-tutor-logs-dev-pooler -U postgres -d dsc10_tutor_logs
```

### Dump DB to Parquet

```bash
# Port-forward directly to the pod (service has no selector, so can't forward to svc)
kubectl port-forward pod/dsc10-tutor-logs-dev-0 5433:5432 -n dsc-10-llm &

# Run the dump script (uses api/ project deps)
DB_HOST=localhost DB_PORT=5433 DB_NAME=dsc10_tutor_logs DB_USER=dsc10_tutor DB_PASSWORD=<password> \
  uv run --project api python api/dump_to_parquet.py events_dev.parquet

# Kill the port-forward when done
kill %1
```

### Logs

```bash
kubectl logs dsc10-tutor-logs-dev-0 -n dsc-10-llm
```

## Important Notes

- The Zalando operator manages StatefulSets, not Deployments (stateful workloads need stable storage/identity)
- **PVCs are deleted when the postgresql resource is deleted** — the operator has `enable_persistent_volume_claim_deletion: true` by default, and this is an operator-level setting (not per-cluster). Back up data before deleting.
- Password changes on every fresh deploy (new PVC = new secrets)
- Internal service DNS: `dsc10-tutor-logs-dev.dsc-10-llm.svc.cluster.local:5432`
- Pooler service DNS: `dsc10-tutor-logs-dev-pooler.dsc-10-llm.svc.cluster.local:5432`
