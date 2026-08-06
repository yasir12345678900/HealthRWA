"""Consent creation and canonical hashing for HALAH."""

from __future__ import annotations

import json
import uuid

from web3 import Web3

from models.consent import Consent


def _unique_clean(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def compute_consent_hash(
    *,
    consent_id: str,
    patient_did: str,
    requester_did: str,
    guardian_dids: list[str],
    scope: list[str],
    purpose: str,
    threshold: int,
    start_date: str,
    expiry_date: str,
) -> str:
    """Returns a deterministic Keccak-256 fingerprint of immutable consent terms."""
    payload = {
        "schema": "HALAH-CONSENT-1",
        "consent_id": consent_id,
        "patient_did": patient_did.strip(),
        "requester_did": requester_did.strip(),
        "guardian_dids": sorted(guardian_dids),
        "scope": sorted(scope),
        "purpose": purpose.strip(),
        "threshold": int(threshold),
        "start_date": start_date,
        "expiry_date": expiry_date,
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return Web3.to_hex(Web3.keccak(text=canonical))


def compute_approval_hash(consent: Consent) -> str:
    """Anchors the exact unique signer set used to satisfy the threshold."""
    payload = {
        "schema": "HALAH-APPROVALS-1",
        "consent_hash": consent.consent_hash,
        "signatures": sorted(set(consent.signatures)),
        "threshold": int(consent.threshold),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return Web3.to_hex(Web3.keccak(text=canonical))


def create_consent(
    patient: str,
    doctor: str,
    guardians: list[str],
    scope: list[str],
    purpose: str,
    start: str,
    expiry: str,
) -> Consent:
    guardian_dids = _unique_clean(guardians)
    data_scope = _unique_clean(scope)

    if len(guardian_dids) < 2:
        raise ValueError("At least two distinct guardians are required.")
    if not data_scope:
        raise ValueError("At least one healthcare data category is required.")
    if not patient.strip() or not doctor.strip():
        raise ValueError("Patient and requester DIDs are required.")

    consent_id = str(uuid.uuid4())
    threshold = len(guardian_dids)
    consent_hash = compute_consent_hash(
        consent_id=consent_id,
        patient_did=patient,
        requester_did=doctor,
        guardian_dids=guardian_dids,
        scope=data_scope,
        purpose=purpose,
        threshold=threshold,
        start_date=start,
        expiry_date=expiry,
    )

    return Consent(
        consent_id=consent_id,
        patient_did=patient.strip(),
        requester_did=doctor.strip(),
        guardian_dids=guardian_dids,
        purpose=purpose.strip(),
        scope=data_scope,
        threshold=threshold,
        consent_hash=consent_hash,
        start_date=start,
        expiry_date=expiry,
        state="PENDING_SIGNATURE",
    )
