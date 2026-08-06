"""End-to-end Web3 smoke test against a running local Hardhat node."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from services.blockchain_service import (
    has_requester_access_on_chain,
    is_consent_valid_on_chain,
    mint_consent_sbt,
    read_on_chain_consent,
    revoke_consent_sbt,
)
from services.consent_service import create_consent


now = datetime.now(timezone.utc).replace(microsecond=0)
consent = create_consent(
    patient="did:patient:ci-demo",
    doctor="did:hospital:ci-demo",
    guardians=["did:parent:A", "did:parent:B"],
    scope=["Medication", "Condition"],
    purpose="Treatment",
    start=(now - timedelta(minutes=1)).isoformat(),
    expiry=(now + timedelta(hours=1)).isoformat(),
)
consent.signatures.extend(consent.guardian_dids)

mint = mint_consent_sbt(consent)
consent.token_id = mint["token_id"]
consent.approval_hash = mint["approval_hash"]
consent.patient_address = mint["patient_address"]
consent.requester_address = mint["requester_address"]
consent.contract_address = mint["contract_address"]
consent.chain_id = mint["chain_id"]
consent.mint_tx_hash = mint["transaction_hash"]
consent.mint_block_number = mint["block_number"]
consent.mint_gas_used = mint["gas_used"]

assert consent.token_id == 1
assert consent.mint_tx_hash.startswith("0x")
assert consent.mint_block_number >= 2
assert consent.mint_gas_used > 0
assert is_consent_valid_on_chain(consent)
assert has_requester_access_on_chain(consent)

on_chain = read_on_chain_consent(consent)
assert on_chain["consent_hash"].lower() == consent.consent_hash.lower()
assert on_chain["approval_hash"].lower() == consent.approval_hash.lower()
assert on_chain["threshold"] == 2
assert on_chain["approval_count"] == 2
assert on_chain["revoked"] is False

revocation = revoke_consent_sbt(consent)
consent.revoked = True
consent.revoke_tx_hash = revocation["transaction_hash"]
consent.revoke_block_number = revocation["block_number"]
consent.revoke_gas_used = revocation["gas_used"]
assert not is_consent_valid_on_chain(consent)

output = {
    "consent_id": consent.consent_id,
    "consent_hash": consent.consent_hash,
    "approval_hash": consent.approval_hash,
    "token_id": consent.token_id,
    "contract_address": consent.contract_address,
    "chain_id": consent.chain_id,
    "mint": mint,
    "on_chain_record": on_chain,
    "revocation": revocation,
    "valid_after_revocation": False,
}

output_path = Path("blockchain/evidence/python-web3-smoke.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
print(json.dumps(output, indent=2))
