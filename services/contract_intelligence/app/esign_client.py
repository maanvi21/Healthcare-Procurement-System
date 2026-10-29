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
import base64

import requests

from app.config import settings

logger = logging.getLogger("contract_intelligence.esign_client")


def send_for_signature(contract_id: str, pdf_bytes: bytes, signer_email: str, signer_name: str, signature_page: int) -> dict:
    if not settings.opensign_api_key:
        if settings.esign_demo_mode:
            return {"object_id": f"demo-{uuid.uuid4()}", "signing_url": None, "provider": "demo"}
        raise RuntimeError("OpenSign API token is not configured; set OPENSIGN_API_KEY or enable explicit demo mode.")
    payload = {
        "file": base64.b64encode(pdf_bytes).decode("ascii"),
        "title": f"MediSource Contract {contract_id}",
        "note": "Please review and sign this procurement contract.",
        "description": f"Contract reference {contract_id}",
        "signers": [{
            "role": "Supplier",
            "name": signer_name,
            "email": signer_email,
            "widgets": [{"type": "signature", "page": signature_page, "x": 72, "y": 620, "w": 240, "h": 55}],
        }],
        "send_email": True,
        "sendInOrder": True,
        "enableOTP": False,
        "auto_reminder": True,
        "remind_once_in_every": 5,
    }
    response = requests.post(
        f"{settings.opensign_base_url.rstrip('/')}/createdocument",
        headers={"x-api-token": settings.opensign_api_key, "Accept": "application/json"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    envelope_id = result.get("objectId")
    if not envelope_id:
        raise RuntimeError(f"OpenSign did not return an objectId: {result}")
    signing_urls = result.get("signurl") or []
    return {
        "object_id": envelope_id,
        "signing_url": next((s.get("url") for s in signing_urls if s.get("email", "").lower() == signer_email.lower()), None),
        "provider": "opensign",
    }
