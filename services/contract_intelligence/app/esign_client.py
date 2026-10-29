"""DocuSign eSignature REST API adapter.

Uses the JWT bearer grant for unattended server-to-server envelope delivery. The
recipient is emailed by DocuSign; Connect completion events are handled separately by
the contracts router and the signed PDF is downloaded through the same authenticated
API before it is archived in MinIO.
"""
import base64
import logging
import time

import jwt
import requests

from app.config import settings

logger = logging.getLogger("contract_intelligence.esign_client")
_TOKEN: str | None = None
_TOKEN_EXPIRES_AT = 0.0
_ACCOUNT: tuple[str, str] | None = None


def _private_key() -> str:
    return (settings.docusign_rsa_private_key or "").replace("\\n", "\n").strip()


def credentials_configured() -> bool:
    return bool(
        settings.docusign_integration_key.strip()
        and settings.docusign_user_id.strip()
        and _private_key().startswith("-----BEGIN")
    )


def connect_configured() -> bool:
    return bool(
        settings.docusign_connect_url.strip().lower().startswith("https://")
        and settings.docusign_connect_hmac_key.strip()
    )


def _oauth_host() -> str:
    return settings.docusign_oauth_host.strip().removeprefix("https://").strip("/")


def _access_token() -> str:
    global _TOKEN, _TOKEN_EXPIRES_AT
    if _TOKEN and time.time() < _TOKEN_EXPIRES_AT - 60:
        return _TOKEN
    if not credentials_configured():
        raise RuntimeError(
            "DocuSign is not configured. Set DOCUSIGN_INTEGRATION_KEY, DOCUSIGN_USER_ID, "
            "and DOCUSIGN_RSA_PRIVATE_KEY in the project environment."
        )
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": settings.docusign_integration_key.strip(),
            "sub": settings.docusign_user_id.strip(),
            "aud": _oauth_host(),
            "iat": now,
            "exp": now + 3600,
            "scope": "signature impersonation",
        },
        _private_key(),
        algorithm="RS256",
    )
    response = requests.post(
        f"https://{_oauth_host()}/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if not response.ok:
        try:
            error = response.json().get("error", "")
        except ValueError:
            error = ""
        if error == "consent_required":
            raise RuntimeError(
                "DocuSign user consent is required. Grant the app's signature and impersonation "
                "permissions to the configured DocuSign user, then retry."
            )
        raise RuntimeError(f"DocuSign OAuth token request failed with HTTP {response.status_code}.")
    try:
        data = response.json()
        _TOKEN = data["access_token"]
        _TOKEN_EXPIRES_AT = time.time() + int(data.get("expires_in", 3600))
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("DocuSign returned an invalid OAuth token response.") from exc
    return _TOKEN


def _account_and_base_url() -> tuple[str, str]:
    global _ACCOUNT
    if _ACCOUNT:
        return _ACCOUNT
    token = _access_token()
    response = requests.get(
        f"https://{_oauth_host()}/oauth/userinfo",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"Could not resolve the DocuSign account API base URL (HTTP {response.status_code}).")
    try:
        accounts = response.json().get("accounts", [])
    except ValueError as exc:
        raise RuntimeError("DocuSign returned invalid account information.") from exc
    account = None
    if settings.docusign_account_id.strip():
        account = next(
            (item for item in accounts if item.get("account_id") == settings.docusign_account_id.strip()),
            None,
        )
        if not account:
            raise RuntimeError("DOCUSIGN_ACCOUNT_ID is not available to the configured DocuSign user.")
    else:
        account = next((item for item in accounts if item.get("is_default")), None)
        account = account or (accounts[0] if accounts else None)
    if not account:
        raise RuntimeError("No DocuSign account is available to the configured user. Check DOCUSIGN_USER_ID and account access.")
    account_id = account.get("account_id", "")
    base = settings.docusign_rest_base_url.strip().rstrip("/")
    if not base:
        base = account.get("base_uri", "").rstrip("/") + "/restapi"
    if not account_id or not base.startswith("https://"):
        raise RuntimeError("DocuSign account ID or REST API base URL is missing. Check DOCUSIGN_ACCOUNT_ID and DOCUSIGN_REST_BASE_URL.")
    _ACCOUNT = (account_id, base)
    return _ACCOUNT


def _api_request(method: str, path: str, **kwargs) -> requests.Response:
    account_id, base = _account_and_base_url()
    response = requests.request(
        method,
        f"{base}/v2.1/accounts/{account_id}{path}",
        headers={"Authorization": f"Bearer {_access_token()}", "Accept": "application/json", **kwargs.pop("headers", {})},
        timeout=30,
        **kwargs,
    )
    if not response.ok:
        raise RuntimeError(f"DocuSign API request failed with HTTP {response.status_code}.")
    return response


def send_for_signature(contract_id: str, pdf_bytes: bytes, signer_email: str, signer_name: str, signature_page: int) -> dict:
    if not credentials_configured():
        raise RuntimeError(
            "DocuSign is not configured. Set DOCUSIGN_INTEGRATION_KEY, DOCUSIGN_USER_ID, "
            "and DOCUSIGN_RSA_PRIVATE_KEY in the project environment."
        )
    if not connect_configured():
        raise RuntimeError(
            "DocuSign Connect is not configured. Set DOCUSIGN_CONNECT_URL to a public HTTPS "
            "callback and DOCUSIGN_CONNECT_HMAC_KEY so completion can update the CPanel."
        )
    signer = {
        "email": signer_email,
        "name": signer_name,
        "recipientId": "1",
        "routingOrder": "1",
        "tabs": {
            "signHereTabs": [{
                "documentId": "1",
                "pageNumber": str(signature_page),
                "xPosition": "72",
                "yPosition": "620",
            }]
        },
    }
    envelope = {
        "emailSubject": f"MediSource contract {contract_id} — signature requested",
        "emailBlurb": "Please review and electronically sign this procurement contract.",
        "documents": [{
            "documentBase64": base64.b64encode(pdf_bytes).decode("ascii"),
            "name": f"MediSource-contract-{contract_id}.pdf",
            "fileExtension": "pdf",
            "documentId": "1",
        }],
        "recipients": {"signers": [signer]},
        "status": "sent",
    }
    if settings.docusign_connect_url.strip():
        envelope["eventNotification"] = {
            "url": settings.docusign_connect_url.strip(),
            "loggingEnabled": "true",
            "requireAcknowledgment": "true",
            "useSoapInterface": "false",
            "includeDocuments": "false",
            "envelopeEvents": [
                {"envelopeEventStatusCode": "completed"},
                {"envelopeEventStatusCode": "declined"},
                {"envelopeEventStatusCode": "voided"},
            ],
        }
    try:
        data = _api_request("POST", "/envelopes", json=envelope).json()
    except requests.RequestException as exc:
        raise RuntimeError("Could not reach the DocuSign API. Check network access and account environment settings.") from exc
    except ValueError as exc:
        raise RuntimeError("DocuSign returned an invalid envelope response.") from exc
    envelope_id = data.get("envelopeId")
    if not envelope_id:
        raise RuntimeError("DocuSign did not return an envelope ID.")
    return {"object_id": envelope_id, "signing_url": None, "provider": "docusign"}


def download_completed_documents(envelope_id: str) -> tuple[bytes, bytes | None]:
    """Fetch the combined signed PDF and, where available, its certificate."""
    signed = _api_request(
        "GET", f"/envelopes/{envelope_id}/documents/combined",
        headers={"Accept": "application/pdf"},
    ).content
    certificate = None
    try:
        certificate = _api_request(
            "GET", f"/envelopes/{envelope_id}/documents/certificate",
            headers={"Accept": "application/pdf"},
        ).content
    except RuntimeError as exc:
        logger.info("DocuSign completion certificate unavailable for envelope %s: %s", envelope_id, exc)
    if not signed.startswith(b"%PDF-"):
        raise RuntimeError("DocuSign returned an invalid completed PDF.")
    return signed, certificate if certificate and certificate.startswith(b"%PDF-") else None
