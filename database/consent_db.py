"""In-memory consent registry for the HALAH proof of concept."""

from __future__ import annotations

from models.consent import Consent


CONSENTS: dict[str, Consent] = {}


def save(consent: Consent) -> None:
    CONSENTS[consent.consent_id] = consent


def get(consent_id: str) -> Consent | None:
    return CONSENTS.get(consent_id.strip())


def update(consent: Consent) -> None:
    CONSENTS[consent.consent_id] = consent


def revoke(consent_id: str) -> Consent | None:
    consent = get(consent_id)
    if consent:
        consent.revoked = True
        consent.state = "REVOKED"
        update(consent)
    return consent


def get_patient_consent(patient: str) -> list[Consent]:
    return [consent for consent in CONSENTS.values() if consent.patient_did == patient]


def all_consents() -> list[Consent]:
    return list(CONSENTS.values())


def clear() -> None:
    CONSENTS.clear()
