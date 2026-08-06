"""Application service for HALAH local Hardhat transactions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from blockchain.contract import ConsentContract
from models.consent import Consent
from services.consent_service import compute_approval_hash


def _unix_timestamp(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def get_blockchain_status() -> dict[str, Any]:
    return ConsentContract().health()


def mint_consent_sbt(consent: Consent) -> dict[str, Any]:
    """Mints a real local SBT after the configured guardian threshold is met."""
    unique_signatures = sorted(set(consent.signatures))
    if len(unique_signatures) < consent.threshold:
        raise ValueError("The guardian approval threshold has not been met.")
    if consent.token_id is not None:
        raise ValueError("This consent has already been minted.")

    contract = ConsentContract()
    patient_address = contract.address_for_did(consent.patient_did, "patient")
    requester_address = contract.address_for_did(consent.requester_did, "requester")
    approval_hash = compute_approval_hash(consent)

    evidence = contract.mint_consent(
        patient_address=patient_address,
        requester_address=requester_address,
        consent_hash=consent.consent_hash,
        approval_hash=approval_hash,
        purpose=consent.purpose,
        valid_from=_unix_timestamp(consent.start_date),
        valid_until=_unix_timestamp(consent.expiry_date),
        threshold=consent.threshold,
        approval_count=len(unique_signatures),
    )

    return {
        **evidence.to_dict(),
        "approval_hash": approval_hash,
        "patient_address": patient_address,
        "requester_address": requester_address,
    }


def revoke_consent_sbt(consent: Consent) -> dict[str, Any]:
    if consent.token_id is None:
        raise ValueError("The consent has no on-chain token to revoke.")
    if consent.revoked:
        raise ValueError("The consent is already revoked.")

    evidence = ConsentContract().revoke(consent.token_id)
    return evidence.to_dict()


def is_consent_valid_on_chain(consent: Consent) -> bool:
    if consent.token_id is None:
        return False
    return ConsentContract().check_valid(consent.token_id)


def has_requester_access_on_chain(consent: Consent) -> bool:
    if consent.token_id is None or not consent.requester_address:
        return False
    return ConsentContract().check_access(
        consent.token_id,
        consent.requester_address,
    )


def read_on_chain_consent(consent: Consent) -> dict[str, Any]:
    if consent.token_id is None:
        raise ValueError("The consent has no on-chain token.")
    return ConsentContract().read_consent(consent.token_id)
