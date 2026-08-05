# One-command local/demo deploy for Windows PowerShell. See deploy.sh for the Linux/Mac
# equivalent — same steps, same order.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".env")) {
    Write-Host "No .env found -- copying .env.example"
    Copy-Item ".env.example" ".env"
}

Write-Host "Building and starting all services (this can take a while on first run -- PaddleOCR/mlflow/kafka images are large)..."
docker compose up -d --build

Write-Host "Waiting for Postgres/Kafka/MinIO health checks..."
foreach ($svc in @("postgres", "kafka", "minio")) {
    while ($true) {
        $cid = docker compose ps -q $svc
        if ($cid) {
            $status = docker inspect -f "{{.State.Health.Status}}" $cid 2>$null
            if ($status -eq "healthy") { break }
        }
        Start-Sleep -Seconds 3
    }
    Write-Host "  $svc is healthy"
}

Write-Host "Declaring Kafka topics..."
$topics = @(
    "documents.ingested", "documents.processed", "vendor.onboarded", "vendor.updated",
    "procurement.request.created", "approval.requested", "approval.approved", "approval.rejected",
    "approval.escalated", "inventory.reserved", "inventory.backorder", "contract.generated",
    "contract.signed", "risk.assessed"
)
foreach ($topic in $topics) {
    Write-Host "  Ensuring topic: $topic"
    docker compose exec -T kafka kafka-topics --bootstrap-server localhost:9092 `
        --create --if-not-exists --topic $topic --partitions 3 --replication-factor 1
}

Write-Host "Waiting for application services to report healthy..."
Start-Sleep -Seconds 10

Write-Host "Loading demo seed data..."
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    python -m pip install --quiet requests reportlab 2>$null
    python scripts/seed-data.py
    $ErrorActionPreference = $oldPreference
} else {
    Write-Host "python not found on PATH -- skipping seed data. Run 'python scripts/seed-data.py' manually once Python is available."
}

Write-Host ""
Write-Host "MediSource AI is up:"
Write-Host "  App:           http://localhost"
Write-Host "  Temporal UI:   http://localhost:8088"
Write-Host "  MLflow UI:     http://localhost:5000"
Write-Host "  MinIO console: http://localhost:9001"
Write-Host "  OPA:           http://localhost:8181"
