"""Web3 adapter for the HALAH local Hardhat consent contract.

This module intentionally accepts only the local Hardhat chain (chain ID 31337)
unless ALLOW_NONLOCAL_BLOCKCHAIN=true is explicitly configured.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from web3 import Web3


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RPC_URL = "http://127.0.0.1:8545"
DEFAULT_DEPLOYMENT_PATH = ROOT_DIR / "blockchain" / "deployment" / "local.json"
ARTIFACT_CANDIDATES = (
    ROOT_DIR
    / "blockchain"
    / "artifacts"
    / "blockchain"
    / "contracts"
    / "ConsentSBT.sol"
    / "ConsentSBT.json",
    ROOT_DIR
    / "blockchain"
    / "artifacts"
    / "contracts"
    / "ConsentSBT.sol"
    / "ConsentSBT.json",
)


class BlockchainError(RuntimeError):
    """Base exception for local blockchain integration failures."""


class BlockchainConnectionError(BlockchainError):
    """Raised when the local Hardhat JSON-RPC endpoint is unavailable."""


class BlockchainConfigurationError(BlockchainError):
    """Raised when deployment metadata or the contract artifact is missing."""


@dataclass(frozen=True)
class TransactionEvidence:
    event_name: str
    transaction_hash: str
    block_number: int
    gas_used: int
    contract_address: str
    chain_id: int
    token_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConsentContract:
    """Typed adapter around the locally deployed ConsentSBT contract."""

    def __init__(
        self,
        rpc_url: str | None = None,
        deployment_path: str | Path | None = None,
    ) -> None:
        self.rpc_url = rpc_url or os.getenv("HARDHAT_RPC_URL", DEFAULT_RPC_URL)
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 10}))

        if not self.w3.is_connected():
            raise BlockchainConnectionError(
                f"Local Hardhat blockchain is not reachable at {self.rpc_url}."
            )

        self.chain_id = int(self.w3.eth.chain_id)
        allow_nonlocal = os.getenv("ALLOW_NONLOCAL_BLOCKCHAIN", "false").lower() == "true"
        if self.chain_id != 31337 and not allow_nonlocal:
            raise BlockchainConfigurationError(
                f"Refusing chain ID {self.chain_id}; HALAH is configured for local Hardhat 31337."
            )

        deployment_file = Path(deployment_path or DEFAULT_DEPLOYMENT_PATH)
        deployment = self._read_json(deployment_file, "deployment metadata")
        configured_address = os.getenv("CONSENT_CONTRACT_ADDRESS")
        address = configured_address or deployment.get("contractAddress")
        if not address:
            raise BlockchainConfigurationError(
                "Contract address is missing. Run npm run deploy:local first."
            )

        artifact_path = next((path for path in ARTIFACT_CANDIDATES if path.exists()), None)
        if artifact_path is None:
            raise BlockchainConfigurationError(
                "ConsentSBT artifact is missing. Run npm run compile first."
            )
        artifact = self._read_json(artifact_path, "contract artifact")
        abi = artifact.get("abi")
        if not abi:
            raise BlockchainConfigurationError("ConsentSBT ABI is missing from the artifact.")

        self.contract_address = Web3.to_checksum_address(address)
        if self.w3.eth.get_code(self.contract_address) in (b"", b"\x00"):
            raise BlockchainConfigurationError(
                f"No contract bytecode exists at {self.contract_address}. Redeploy locally."
            )

        self.contract = self.w3.eth.contract(address=self.contract_address, abi=abi)
        self.accounts = [Web3.to_checksum_address(value) for value in self.w3.eth.accounts]
        if len(self.accounts) < 3:
            raise BlockchainConfigurationError(
                "At least three unlocked Hardhat accounts are required."
            )
        self.owner_address = self.accounts[0]

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not path.exists():
            raise BlockchainConfigurationError(f"Missing {label}: {path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise BlockchainConfigurationError(f"Invalid {label}: {path}") from exc

    def address_for_did(self, did: str, role: str) -> str:
        """Deterministically maps a demo DID to an unlocked local Hardhat account."""
        normalized_role = role.strip().lower()
        if normalized_role == "patient":
            pool = self.accounts[1:10] or self.accounts[1:]
        elif normalized_role in {"doctor", "requester"}:
            pool = self.accounts[10:19] or self.accounts[2:]
        else:
            pool = self.accounts[1:]

        digest = hashlib.sha256(did.strip().encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % len(pool)
        return pool[index]

    def health(self) -> dict[str, Any]:
        latest = self.w3.eth.get_block("latest")
        return {
            "connected": True,
            "rpc_url": self.rpc_url,
            "chain_id": self.chain_id,
            "latest_block": int(latest["number"]),
            "contract_address": self.contract_address,
            "owner_address": self.owner_address,
        }

    def mint_consent(
        self,
        *,
        patient_address: str,
        requester_address: str,
        consent_hash: str,
        approval_hash: str,
        purpose: str,
        valid_from: int,
        valid_until: int,
        threshold: int,
        approval_count: int,
    ) -> TransactionEvidence:
        tx_hash = self.contract.functions.mintConsent(
            Web3.to_checksum_address(patient_address),
            Web3.to_checksum_address(requester_address),
            Web3.to_bytes(hexstr=consent_hash),
            Web3.to_bytes(hexstr=approval_hash),
            purpose,
            int(valid_from),
            int(valid_until),
            int(threshold),
            int(approval_count),
        ).transact({"from": self.owner_address})

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        events = self.contract.events.ConsentIssued().process_receipt(receipt)
        if not events:
            raise BlockchainError("ConsentIssued event was not emitted.")
        token_id = int(events[0]["args"]["tokenId"])

        return TransactionEvidence(
            event_name="ConsentIssued",
            transaction_hash=Web3.to_hex(receipt["transactionHash"]),
            block_number=int(receipt["blockNumber"]),
            gas_used=int(receipt["gasUsed"]),
            contract_address=self.contract_address,
            chain_id=self.chain_id,
            token_id=token_id,
        )

    def revoke(self, token_id: int) -> TransactionEvidence:
        tx_hash = self.contract.functions.revoke(int(token_id)).transact(
            {"from": self.owner_address}
        )
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        events = self.contract.events.ConsentRevoked().process_receipt(receipt)
        if not events:
            raise BlockchainError("ConsentRevoked event was not emitted.")

        return TransactionEvidence(
            event_name="ConsentRevoked",
            transaction_hash=Web3.to_hex(receipt["transactionHash"]),
            block_number=int(receipt["blockNumber"]),
            gas_used=int(receipt["gasUsed"]),
            contract_address=self.contract_address,
            chain_id=self.chain_id,
            token_id=int(token_id),
        )

    def check_valid(self, token_id: int) -> bool:
        return bool(self.contract.functions.checkValid(int(token_id)).call())

    def check_access(self, token_id: int, requester_address: str) -> bool:
        return bool(
            self.contract.functions.checkAccess(
                int(token_id), Web3.to_checksum_address(requester_address)
            ).call()
        )

    def read_consent(self, token_id: int) -> dict[str, Any]:
        values = self.contract.functions.consents(int(token_id)).call()
        return {
            "patient_address": values[0],
            "requester_address": values[1],
            "consent_hash": Web3.to_hex(values[2]),
            "approval_hash": Web3.to_hex(values[3]),
            "purpose": values[4],
            "valid_from": int(values[5]),
            "valid_until": int(values[6]),
            "threshold": int(values[7]),
            "approval_count": int(values[8]),
            "revoked": bool(values[9]),
        }
