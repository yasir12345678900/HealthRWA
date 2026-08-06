"""Consent data model for the HALAH proof of concept."""

from dataclasses import dataclass, field


@dataclass
class Consent:
    consent_id: str
    patient_did: str
    requester_did: str
    guardian_dids: list[str]
    purpose: str
    scope: list[str]
    threshold: int
    consent_hash: str
    signatures: list[str] = field(default_factory=list)
    start_date: str | None = None
    expiry_date: str | None = None
    state: str = "CREATED"
    revoked: bool = False

    # Multi-party evidence anchored with the SBT.
    approval_hash: str | None = None

    # Local Hardhat / SBT evidence.
    token_id: int | None = None
    patient_address: str | None = None
    requester_address: str | None = None
    contract_address: str | None = None
    chain_id: int | None = None

    mint_tx_hash: str | None = None
    mint_block_number: int | None = None
    mint_gas_used: int | None = None

    revoke_tx_hash: str | None = None
    revoke_block_number: int | None = None
    revoke_gas_used: int | None = None
