# Architecture diagrams

The rendered diagrams live in `docs/diagrams/`. These scripts generate them, so a diagram
can be corrected when the architecture changes rather than being an undated binary nobody
can edit.

| Script | Produces |
|---|---|
| `risk_ml_layer.py` | The risk agent's ML layer — all 17 features, both models, the banding rule |
| `approval_workflow.py` | OPA routing, the sequential approver chain, and all three exits |

Each writes an SVG to `/out`. Numbers in them (feature importances, hyperparameters, SLA
hours) were read from the running system — if you change the model or the policy, re-read
them before regenerating.

## Regenerate

Run in a container so no host dependencies are needed:

```bash
cd "$(git rev-parse --show-toplevel)"
docker run --rm -v "$PWD/scripts/diagrams:/gen:ro" -v "$PWD/docs/diagrams:/out" \
  python:3.11-slim python /gen/risk_ml_layer.py

docker run --rm -v "$PWD/scripts/diagrams:/gen:ro" -v "$PWD/docs/diagrams:/out" \
  python:3.11-slim python /gen/approval_workflow.py
```

Then convert to PNG for slides:

```bash
docker run --rm -v "$PWD/docs/diagrams:/out" python:3.11-slim bash -c '
  apt-get update -qq && apt-get install -y -qq libcairo2 && pip install -q cairosvg
  python -c "
import cairosvg
for n in (\"risk_ml_layer\", \"approval_workflow\"):
    cairosvg.svg2png(url=f\"/out/{n}.svg\", write_to=f\"/out/{n}.png\", scale=2.0)
"'
```

Docker writes as root; fix ownership afterwards with
`sudo chown "$USER:$USER" docs/diagrams/*`.
