# Deployment guide

Three target platforms with concrete steps. All assume:
- Supabase project already exists; schema applied via `database/schema.sql`.
- `.env` filled in (see `.env.example`).
- Docker image builds locally (`docker compose build`).

---

## 1 · Railway

Railway is the fastest path — auto-detects the Dockerfile.

```bash
# CLI install (one-time)
npm i -g @railway/cli && railway login

# From the project root:
railway init                                # creates a new project
railway up                                  # builds & deploys
```

Then:
1. **Add Redis** — Railway → New → Database → Redis. Copy `REDIS_URL`.
2. **Environment vars** — paste your `.env` into the Variables tab.
3. **Split the worker** — duplicate the service, set `start command`
   to `worker` (uses `docker/entrypoint.sh`). Disable HTTP on the
   worker (Settings → Networking → no public domain).
4. **Cron freshness** — Railway containers can sleep; ensure the
   worker service has **autosleep disabled**.

Cost: ~$5–10/mo for API + worker + Redis (Hobby plan).

---

## 2 · Render

Render's "Blueprint" file gives a one-click multi-service deploy.

Create `render.yaml` at the repo root:

```yaml
services:
  - type: web
    name: market-api
    runtime: docker
    dockerfilePath: docker/Dockerfile
    dockerCommand: api
    envVars:
      - key: ENV
        value: production
      - key: SCHEDULER_ENABLED
        value: "false"
      - fromGroup: market-pipeline
    healthCheckPath: /health

  - type: worker
    name: market-worker
    runtime: docker
    dockerfilePath: docker/Dockerfile
    dockerCommand: worker
    envVars:
      - key: SCHEDULER_ENABLED
        value: "true"
      - fromGroup: market-pipeline

  - type: keyvalue
    name: market-redis
    plan: starter
    maxmemoryPolicy: allkeys-lru

envVarGroups:
  - name: market-pipeline
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: ADMIN_API_KEY
        sync: false
```

Then **New → Blueprint → connect repo → apply**.

---

## 3 · AWS ECS Fargate

Production-grade, more setup.

### Build & push image

```bash
aws ecr create-repository --repository-name market-pipeline

# Tag & push
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=ap-south-1
REPO=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/market-pipeline

aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $REPO

docker build -t $REPO:latest -f docker/Dockerfile .
docker push $REPO:latest
```

### Secrets

```bash
aws secretsmanager create-secret \
  --name market-pipeline/env \
  --secret-string file://.env.json
```

### Task definitions

Create two task defs — one per process:

| Service        | Command   | CPU  | Memory | Replicas | Notes                          |
|----------------|-----------|------|--------|----------|--------------------------------|
| `market-api`   | `api`     | 512  | 1024   | 2–4      | behind ALB, target group :8000 |
| `market-worker`| `worker`  | 1024 | 2048   | 1        | no inbound, scheduler only     |

Both pull secrets via `secretsManagerArn`. Use the same image and the
`command` argument to switch process modes.

### ALB + DNS

- Target group → `market-api` → port `8000`, health check `/health`.
- ACM certificate → ALB listener `:443`.
- Route 53 → A-ALIAS to the ALB.

### Redis

Use **ElastiCache Redis** (`cache.t4g.micro` for staging). Add its
endpoint to the secret as `REDIS_URL`.

### Observability

- CloudWatch Logs picks up stdout from both services (structlog JSON).
- Add a Prometheus sidecar **or** scrape `/metrics` with
  `aws-otel-collector` → AMP.

---

## Checklist before going live

- [ ] `ADMIN_API_KEY` rotated from default
- [ ] `DATABASE_URL` points at production Supabase, not dev
- [ ] Supabase RLS policies applied (re-run `schema.sql` — idempotent)
- [ ] Scheduler runs in **exactly one** worker replica (APScheduler is
      in-memory; coordinating multiple workers requires a Redis job store
      — not currently configured)
- [ ] `/metrics` reachable by Prometheus (private network or auth)
- [ ] Grafana dashboard imported; alerts wired to `ALERT_WEBHOOK_URL`
- [ ] Backup strategy for Supabase: enable Point-in-Time Recovery
- [ ] Log retention configured (CloudWatch / Railway / Render defaults
      are usually adequate)
