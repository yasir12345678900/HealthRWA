"""Consent lifecycle state machine for HALAH."""

from __future__ import annotations

from datetime import datetime, timezone

from models.consent import Consent


def _as_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_state(consent: Consent, now: datetime | None = None) -> str:
    """Evaluate threshold, blockchain issuance, validity window, and revocation."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    if consent.revoked:
        consent.state = "REVOKED"
    elif len(set(consent.signatures)) < consent.threshold:
        consent.state = "PENDING_SIGNATURE"
    elif consent.token_id is None:
        consent.state = "PENDING_BLOCKCHAIN"
    elif consent.start_date and current < _as_utc(consent.start_date):
        consent.state = "NOT_STARTED"
    elif consent.expiry_date and current > _as_utc(consent.expiry_date):
        consent.state = "EXPIRED"
    else:
        consent.state = "ACTIVE"

    return consent.state
