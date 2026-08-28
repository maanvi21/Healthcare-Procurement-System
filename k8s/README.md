# Kubernetes Deployment

Production-shaped deployment matching `docker-compose.yml`'s topology: Postgres (one
instance, database-per-service), Redis, Kafka + Zookeeper, MinIO, OPA, Temporal (+ UI),
MLflow, the seven FastAPI services, the React frontend, and an Nginx gateway fronting
everything, exposed via an Ingress.

## 1. Build and load images

Using [kind](https://kind.sigs.k8s.io/) for a local cluster:

```bash
kind create cluster --name medisource

# build every service image
docker build -t medisource/document-intelligence:latest services/document_intelligence
docker build -t medisource/vendor-intelligence:latest services/vendor_intelligence
docker build -t medisource/approval-workflow:latest services/approval_workflow
docker build -t medisource/inventory-intelligence:latest services/inventory_intelligence
docker build -t medisource/contract-intelligence:latest services/contract_intelligence
docker build -t medisource/risk-intelligence:latest services/risk_intelligence
docker build -t medisource/notification-agent:latest services/notification_agent
docker build -t medisource/frontend:latest frontend
docker build -t medisource/mlflow:latest infra/mlflow

# load them into the kind cluster (kind doesn't pull from a registry by default)
for img in document-intelligence vendor-intelligence approval-workflow inventory-intelligence \
           contract-intelligence risk-intelligence notification-agent frontend mlflow; do
  kind load docker-image medisource/$img:latest --name medisource
done
```

For a real cluster, push these images to a registry instead and update the `image:`
fields in `k8s/*.yaml` / `k8s/services/*.yaml` accordingly.

## 2. Apply the manifests

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml -f k8s/secret.yaml
kubectl apply -f k8s/postgres.yaml -f k8s/redis.yaml -f k8s/zookeeper.yaml -f k8s/kafka.yaml \
               -f k8s/minio.yaml -f k8s/opa.yaml -f k8s/temporal.yaml -f k8s/mlflow.yaml
kubectl -n medisource wait --for=condition=ready pod -l app=postgres --timeout=180s

kubectl apply -f k8s/services/
kubectl apply -f k8s/frontend.yaml -f k8s/gateway.yaml -f k8s/ingress.yaml
```

An [nginx ingress controller](https://kubernetes.github.io/ingress-nginx/) must already
be installed on the cluster for `k8s/ingress.yaml` to do anything; for `kind`, see
https://kind.sigs.k8s.io/docs/user/ingress/. Once it's routing, add
`127.0.0.1 medisource.local` to your hosts file and open `http://medisource.local`.

Without an ingress controller, `kubectl -n medisource port-forward svc/gateway 8080:80`
and open `http://localhost:8080` works just as well for a demo.

## 3. Notes

- **Secrets** (`k8s/secret.yaml`, per-service `*-db` Secrets) ship with demo credentials
  in plaintext `stringData`/base64 for a working `kubectl apply` out of the box — replace
  with a real secrets manager before any non-local deployment.
- **DNS naming**: services here use hyphenated names (`document-intelligence`) because
  Kubernetes Service names must be valid RFC 1123 DNS labels, whereas
  `docker-compose.yml` uses underscored names (`document_intelligence`); `k8s/gateway.yaml`
  ships its own copy of the Nginx routing config for this reason (see the comment at its
  top) rather than reusing `gateway/nginx.conf` directly.
- **Storage**: Postgres/MinIO/MLflow use `PersistentVolumeClaim`s with default
  `ReadWriteOnce` — fine for a single-node demo cluster; a real deployment would pin a
  `StorageClass` and consider `ReadWriteMany` where a service needs to scale beyond one
  replica (notably MinIO in a multi-replica setup).
- **Scaling**: every service Deployment is `replicas: 1` here for a straightforward
  demo; horizontal scaling is safe for the stateless services (all state lives in
  Postgres/Redis/Kafka/MinIO) — bump `replicas` and add a `HorizontalPodAutoscaler` if
  needed, but that (along with Prometheus/Grafana-based autoscaling metrics) was
  explicitly out of scope for this build's "minimal deploy layer."
