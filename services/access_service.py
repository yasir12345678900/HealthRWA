"""Fine-grained patient-data access checks for HALAH."""

from __future__ import annotations

from models.access import AccessRequest
from models.consent import Consent


def check_scope(consent: Consent, request: AccessRequest) -> bool:
    requested = set(request.scope)
    authorised = set(consent.scope)
    return bool(requested) and requested.issubset(authorised)


def authorize(
    *,
    state: str,
    scope_valid: bool,
    on_chain_valid: bool,
    requester_authorised: bool,
) -> bool:
    """Grant only when application and local smart-contract checks agree."""
    return (
        state == "ACTIVE"
        and scope_valid
        and on_chain_valid
        and requester_authorised
    )
