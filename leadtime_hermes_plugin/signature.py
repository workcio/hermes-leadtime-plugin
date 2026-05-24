from __future__ import annotations

import hmac
from hashlib import sha256


def verify_leadtime_signature(raw_body: bytes, secret: str, signature: str | None, timestamp: str | None) -> bool:
    if not raw_body or not secret or not signature or not timestamp:
        return False
    expected_digest = sign_leadtime_payload(raw_body, secret, timestamp)
    candidates = signature_candidates(signature)
    return any(hmac.compare_digest(expected_digest, candidate) for candidate in candidates)


def sign_leadtime_payload(raw_body: bytes, secret: str, timestamp: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), digestmod=sha256)
    mac.update(timestamp.encode("utf-8"))
    mac.update(b".")
    mac.update(raw_body)
    return mac.hexdigest()


def signature_candidates(signature: str) -> list[str]:
    candidates = [signature]
    if signature.startswith("sha256="):
        candidates.append(signature.removeprefix("sha256="))
    if "v1=" in signature:
        for part in signature.split(","):
            key, _, value = part.strip().partition("=")
            if key == "v1" and value:
                candidates.append(value)
    return candidates
