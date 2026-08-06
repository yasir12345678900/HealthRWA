"""In-memory audit log used by the HALAH proof of concept."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid


AUDIT: list[dict[str, Any]] = []


def log(
    actor_did: str,
    actor_role: str,
    action: str,
    patient_did: str,
    consent_id: str,
    scope: list[str] | None = None,
    purpose: str | None = None,
    result: str = "SUCCESS",
    metadata: dict[str, Any] | None = None,
    tx_hash: str | None = None,
    block_number: int | None = None,
    gas_used: int | None = None,
    token_id: int | None = None,
    contract_address: str | None = None,
    chain_id: int | None = None,
    consent_hash: str | None = None,
    event_name: str | None = None,
) -> None:
    """Append one immutable-style audit event with optional chain evidence."""
    AUDIT.append(
        {
            "event_id": str(uuid.uuid4()),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "actor_did": actor_did,
            "actor_role": actor_role,
            "action": action,
            "patient_did": patient_did,
            "consent_id": consent_id,
            "consent_hash": consent_hash,
            "scope": scope,
            "purpose": purpose,
            "result": result,
            "event_name": event_name,
            "token_id": token_id,
            "tx_hash": tx_hash,
            "block_number": block_number,
            "gas_used": gas_used,
            "contract_address": contract_address,
            "chain_id": chain_id,
            "metadata": metadata,
        }
    )


def get() -> list[dict[str, Any]]:
    return list(AUDIT)


def clear() -> None:
    AUDIT.clear()
