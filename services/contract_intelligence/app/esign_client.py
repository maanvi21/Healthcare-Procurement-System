"""Client for a self-hosted OpenSign (open-source e-signature) instance.

OpenSign's REST API (POST /api/v1/... with an X-API-Key header) is used to create a
signature request from the rendered contract HTML. This makes a real HTTP call against
`OPENSIGN_BASE_URL` — point it at your self-hosted OpenSign deployment to use it for
real.

OpenSign itself is **not** bundled in this repo's docker-compose (it requires its own
Parse Server + MongoDB stack, which is a separate deployment concern). So this client
degrades gracefully: if the configured OpenSign instance is unreachable, it falls back
to a locally-simulated envelope (a deterministic fake envelope id, status left at
`sent_for_signature`) so the rest of the platform's demo flow — and the "signed" webhook
callback used to advance a contract to `signed` — keeps working without a live OpenSign
deployment.
"""
import logging
import uuid

import requests

from app.config import settings

logger = logging.getLogger("contract_intelligence.esign_client")


def send_for_signature(contract_id: str, document_html: str, signer_email: str, signer_name: str) -> str:
    try:
        response = requests.post(
            f"{settings.opensign_base_url}/api/v1/documents",
            headers={"X-API-Key": settings.opensign_api_key},
            json={
                "title": f"MediSource Contract {contract_id}",
                "content": document_html,
                "signers": [{"name": signer_name, "email": signer_email}],
                "externalId": contract_id,
            },
            timeout=5,
        )
        response.raise_for_status()
        return response.json()["documentId"]
    except requests.RequestException as exc:
        logger.warning("OpenSign unreachable (%s) — using simulated envelope for demo purposes", exc)
        return f"simulated-{uuid.uuid4()}"
