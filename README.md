# fastapi-devops-demo

A minimal, fully-typed FastAPI service meant to be used as a **base project for
learning/building a CI/CD and observability pipeline**. It's not trying to
solve a real business problem — every endpoint exists to simulate a class of
operational behavior you'll want to practice observing, alerting on, and
deploying safely: latency, errors, CPU load, memory pressure, health checks,
and structured/correlated logs.

Requires **Python 3.11+**.

## Features

- Fully typed (PEP 604 `X | None` unions, Pydantic v2 models)
- Structured logging with a `request_id` correlated across each request (via
  `contextvars`), plus an `X-Request-ID` response header — JSON in production,
  human-readable text locally
- Prometheus metrics exposed at `/metrics` (via `prometheus-fastapi-instrumentator`)
- Liveness/readiness probes suitable for Kubernetes/ECS/etc.
- Endpoints that simulate latency, random errors, CPU load, and memory pressure
- Dockerfile (non-root user, healthcheck)
- Kubernetes manifests (`k8s/`) — namespace, ConfigMap, Deployment with
  liveness/readiness probes wired up, Service, HPA, Ingress
- A Helm chart (`helm/devops-demo-app/`) covering the same resources, parameterized via `values.yaml`
- pytest test suite, ruff linting, mypy strict typing — a GitHub Actions
  workflow runs all three on every push/PR to `main`

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

uvicorn app.main:app --reload
```

`requirements-dev.txt` pulls in `requirements.txt` plus `pytest`, `httpx`,
`ruff`, and `mypy`. If you only want to run the app, `pip install -r
requirements.txt` is enough.

Then open:

- Interactive docs: <http://localhost:8000/docs>
- Metrics: <http://localhost:8000/metrics>

## Running with Docker

```bash
docker build -t fastapi-devops-demo .
docker run -p 8000:8000 fastapi-devops-demo
```

Or via docker-compose:

```bash
docker compose up --build
```

- App: <http://localhost:8000>

## Running on Kubernetes

The manifests in `k8s/` assume an image published as `samirsomer/devops-demo-app`
and deploy into a dedicated `devops-demo` namespace:

```bash
kubectl apply -f k8s/namespace.yml
kubectl apply -f k8s/configmap.yml
kubectl apply -f k8s/deployment.yml
kubectl apply -f k8s/service.yml
kubectl apply -f k8s/hpa.yml
kubectl apply -f k8s/ingress.yml
```

### Helm

A chart with the same set of resources — parameterized, and with the HPA and
Ingress each toggleable — lives in `helm/devops-demo-app/`:

```bash
helm install devops-demo helm/devops-demo-app \
  --namespace devops-demo --create-namespace
```

Override any `values.yaml` field with `--set` or `-f`, e.g. to disable
autoscaling and run a fixed replica count:

```bash
helm install devops-demo helm/devops-demo-app \
  --namespace devops-demo --create-namespace \
  --set autoscaling.enabled=false --set replicaCount=1
```

## Configuration

All settings are environment variables prefixed with `DEMO_APP_` (see
`app/core/config.py`), and can also be supplied via a local `.env` file.

| Variable                        | Default               | Description                                |
|----------------------------------|------------------------|---------------------------------------------|
| `DEMO_APP_APP_NAME`               | `devops-demo-app`      | Service name                                |
| `DEMO_APP_APP_VERSION`            | `0.1.0`                | Typically injected by CI from a git tag     |
| `DEMO_APP_ENVIRONMENT`            | `local`                | `local` / `staging` / `prod`, etc.          |
| `DEMO_APP_LOG_LEVEL`              | `INFO`                 | Python logging level                        |
| `DEMO_APP_LOG_JSON`               | `false`                | JSON logs (prod) vs. readable text (dev)    |
| `DEMO_APP_DEFAULT_MIN_DELAY_MS`   | `50`                   | Default lower bound for `/simulate/delay`   |
| `DEMO_APP_DEFAULT_MAX_DELAY_MS`   | `500`                  | Default upper bound for `/simulate/delay`   |
| `DEMO_APP_DEFAULT_ERROR_RATE`     | `0.2`                  | Default probability for `/simulate/error`   |

## Endpoints

### Health & meta

| Method | Path            | Purpose                                                                     |
|--------|-----------------|-------------------------------------------------------------------------------|
| GET    | `/health/live`  | Liveness probe — always `200` unless the process is dead                     |
| GET    | `/health/ready` | Readiness probe — randomly returns `503` ~5% of the time to simulate a flaky dependency |
| GET    | `/version`      | App name/version/environment + Python version, for verifying a deployment    |
| GET    | `/metrics`      | Prometheus scrape endpoint                                                   |

### Operational simulation (`/simulate/*`)

| Method | Path                      | Purpose                                                                             |
|--------|---------------------------|----------------------------------------------------------------------------------------|
| GET    | `/simulate/delay`         | Sleeps for a random duration (`min_ms`/`max_ms` query params) — test timeouts & latency dashboards |
| GET    | `/simulate/error`         | Randomly returns a `400/404/429/500/503` (`error_rate` query param, 0-1) — test retries, alerting |
| GET    | `/simulate/cpu`           | Runs a CPU-bound prime sieve (`iterations` query param) — test autoscaling on CPU     |
| GET    | `/simulate/memory`        | Allocates & briefly holds memory (`size_mb`, `hold_ms`) — test memory limits/OOM alerting |
| GET    | `/simulate/status/{code}` | Deterministically returns the given HTTP status code — for scripted synthetic checks  |
| POST   | `/simulate/echo`          | Echoes the JSON body back along with the request's correlation id                    |

Example:

```bash
curl "http://localhost:8000/simulate/delay?min_ms=100&max_ms=1000"
curl "http://localhost:8000/simulate/error?error_rate=0.5"
curl "http://localhost:8000/simulate/cpu?iterations=500000"
curl -X POST http://localhost:8000/simulate/echo -H "Content-Type: application/json" -d '{"message": "hi"}'
```

## Tests, lint, and type checking

```bash
pytest -v
ruff check app tests
mypy app --strict
```

The test suite is intentionally lightweight — it checks status codes and
response shapes rather than business logic (there isn't much of it). All
three commands run in CI on every push/PR to `main`.
