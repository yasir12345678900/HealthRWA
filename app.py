"""HALAH local-blockchain patient consent proof of concept."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from blockchain.contract import BlockchainError
from database import audit_db, consent_db
from database.repository import SyntheaRepository
from models.access import AccessRequest
from services.access_service import authorize, check_scope
from services.blockchain_service import (
    get_blockchain_status,
    has_requester_access_on_chain,
    is_consent_valid_on_chain,
    mint_consent_sbt,
    read_on_chain_consent,
    revoke_consent_sbt,
)
from services.consent_service import create_consent
from services.identity_service import verify_vc
from services.state_service import evaluate_state


DATA_SCOPES = ["Observation", "Medication", "Condition", "Procedure"]
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

st.set_page_config(page_title="HALAH Consent PoC", layout="wide")
repo = SyntheaRepository("data/synthea")
patient_rows = repo.get_patient_dids()
patient_dids = patient_rows["DID"].tolist()


def parse_utc(value: str) -> datetime:
    return datetime.strptime(value, DATE_FORMAT).replace(tzinfo=timezone.utc)


def show_chain_evidence(consent, *, revoked: bool = False) -> None:
    if consent.token_id is None:
        st.info("No SBT has been minted for this consent yet.")
        return

    prefix = "revoke" if revoked else "mint"
    transaction_hash = getattr(consent, f"{prefix}_tx_hash")
    block_number = getattr(consent, f"{prefix}_block_number")
    gas_used = getattr(consent, f"{prefix}_gas_used")

    first, second, third, fourth = st.columns(4)
    first.metric("Token ID", consent.token_id)
    second.metric("Block", block_number if block_number is not None else "—")
    third.metric("Gas used", gas_used if gas_used is not None else "—")
    fourth.metric("Chain ID", consent.chain_id if consent.chain_id is not None else "—")
    st.caption(f"Contract: {consent.contract_address or '—'}")
    st.code(transaction_hash or "No transaction hash", language=None)


def record_mint(consent) -> bool:
    try:
        evidence = mint_consent_sbt(consent)
    except (BlockchainError, ValueError) as exc:
        consent.state = "PENDING_BLOCKCHAIN"
        consent_db.update(consent)
        audit_db.log(
            actor_did="did:halah:smart-contract",
            actor_role="SmartContract",
            action="MINT_SBT",
            patient_did=consent.patient_did,
            consent_id=consent.consent_id,
            consent_hash=consent.consent_hash,
            scope=consent.scope,
            purpose=consent.purpose,
            result="FAILURE",
            metadata={"error": str(exc)},
        )
        st.error(f"SBT minting failed: {exc}")
        return False

    consent.token_id = evidence["token_id"]
    consent.approval_hash = evidence["approval_hash"]
    consent.patient_address = evidence["patient_address"]
    consent.requester_address = evidence["requester_address"]
    consent.contract_address = evidence["contract_address"]
    consent.chain_id = evidence["chain_id"]
    consent.mint_tx_hash = evidence["transaction_hash"]
    consent.mint_block_number = evidence["block_number"]
    consent.mint_gas_used = evidence["gas_used"]
    evaluate_state(consent)
    consent_db.update(consent)

    audit_db.log(
        actor_did="did:halah:smart-contract",
        actor_role="SmartContract",
        action="MINT_SBT",
        patient_did=consent.patient_did,
        consent_id=consent.consent_id,
        consent_hash=consent.consent_hash,
        scope=consent.scope,
        purpose=consent.purpose,
        result="SUCCESS",
        event_name=evidence["event_name"],
        token_id=evidence["token_id"],
        tx_hash=evidence["transaction_hash"],
        block_number=evidence["block_number"],
        gas_used=evidence["gas_used"],
        contract_address=evidence["contract_address"],
        chain_id=evidence["chain_id"],
        metadata={
            "approval_hash": evidence["approval_hash"],
            "threshold": consent.threshold,
            "approval_count": len(set(consent.signatures)),
            "patient_address": evidence["patient_address"],
            "requester_address": evidence["requester_address"],
        },
    )
    st.success("A real local ERC-5484-style consent SBT was minted.")
    show_chain_evidence(consent)
    return True


st.title("HALAH Blockchain Patient Consent Management")
st.caption(
    "Local Hardhat proof of concept: multi-party approval, time-conditional access, "
    "bounded healthcare data scope, SBT issuance, revocation, and auditable chain evidence."
)

role = st.sidebar.selectbox("Role", ["Patient", "Guardian", "Doctor", "Auditor"])

try:
    chain_status = get_blockchain_status()
    st.sidebar.success("Local Hardhat connected")
    st.sidebar.caption(
        f"Chain {chain_status['chain_id']} · Block {chain_status['latest_block']}"
    )
    st.sidebar.code(chain_status["contract_address"], language=None)
except BlockchainError as exc:
    chain_status = None
    st.sidebar.error("Local Hardhat is not ready")
    st.sidebar.caption(str(exc))


if role == "Patient":
    create_tab, revoke_tab = st.tabs(["Create Consent", "Revoke Consent"])

    with create_tab:
        st.header("Create Consent")
        patient_did = st.selectbox("Patient DID", patient_dids, key="create_patient")
        requester_did = st.text_input("Doctor DID", "did:hospital:001")
        guardians_text = st.text_area(
            "Guardian DIDs",
            "did:parent:A,did:parent:B",
            help="Enter at least two distinct DIDs separated by commas.",
        )
        scope = st.multiselect(
            "Authorised Data Scope",
            DATA_SCOPES,
            default=["Medication", "Condition"],
        )

        st.subheader("Consent Validity — UTC")
        current_utc = datetime.now(timezone.utc).replace(microsecond=0)
        start_text = st.text_input(
            "Start Time (YYYY-MM-DD HH:MM:SS UTC)",
            current_utc.strftime(DATE_FORMAT),
        )
        expiry_text = st.text_input(
            "Expiry Time (YYYY-MM-DD HH:MM:SS UTC)",
            (current_utc + timedelta(hours=10)).strftime(DATE_FORMAT),
        )

        if st.button("Create Consent", type="primary"):
            try:
                start_datetime = parse_utc(start_text)
                expiry_datetime = parse_utc(expiry_text)
                if expiry_datetime <= start_datetime:
                    raise ValueError("Expiry time must be later than start time.")

                consent = create_consent(
                    patient_did,
                    requester_did,
                    guardians_text.split(","),
                    scope,
                    "Treatment",
                    start_datetime.isoformat(),
                    expiry_datetime.isoformat(),
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                consent_db.save(consent)
                audit_db.log(
                    actor_did=patient_did,
                    actor_role="Patient",
                    action="CREATE_CONSENT",
                    patient_did=patient_did,
                    consent_id=consent.consent_id,
                    consent_hash=consent.consent_hash,
                    scope=consent.scope,
                    purpose=consent.purpose,
                    result="SUCCESS",
                    metadata={
                        "guardian_dids": consent.guardian_dids,
                        "threshold": consent.threshold,
                        "valid_from": consent.start_date,
                        "valid_until": consent.expiry_date,
                    },
                )
                st.success("Consent record created.")
                st.write("Consent ID")
                st.code(consent.consent_id, language=None)
                st.write("Keccak-256 Consent Hash")
                st.code(consent.consent_hash, language=None)
                st.info(
                    f"State: {consent.state}. The SBT will be minted only after "
                    f"{consent.threshold} distinct guardian approvals."
                )

    with revoke_tab:
        st.header("Revoke On-Chain Consent")
        revoking_patient = st.selectbox(
            "Patient DID",
            patient_dids,
            key="revoke_patient",
        )
        revoke_id = st.text_input("Consent ID to revoke")
        consent = consent_db.get(revoke_id) if revoke_id else None

        if consent:
            st.write(f"Current state: **{evaluate_state(consent)}**")
            show_chain_evidence(consent)

        if st.button("Revoke Consent"):
            if not consent:
                st.error("Consent ID was not found.")
            elif consent.patient_did != revoking_patient:
                st.error("The selected patient does not own this consent record.")
            else:
                try:
                    evidence = revoke_consent_sbt(consent)
                except (BlockchainError, ValueError) as exc:
                    st.error(f"Revocation failed: {exc}")
                else:
                    consent.revoked = True
                    consent.state = "REVOKED"
                    consent.contract_address = evidence["contract_address"]
                    consent.chain_id = evidence["chain_id"]
                    consent.revoke_tx_hash = evidence["transaction_hash"]
                    consent.revoke_block_number = evidence["block_number"]
                    consent.revoke_gas_used = evidence["gas_used"]
                    consent_db.update(consent)
                    audit_db.log(
                        actor_did=revoking_patient,
                        actor_role="Patient",
                        action="REVOKE_CONSENT",
                        patient_did=consent.patient_did,
                        consent_id=consent.consent_id,
                        consent_hash=consent.consent_hash,
                        scope=consent.scope,
                        purpose=consent.purpose,
                        result="SUCCESS",
                        event_name=evidence["event_name"],
                        token_id=consent.token_id,
                        tx_hash=evidence["transaction_hash"],
                        block_number=evidence["block_number"],
                        gas_used=evidence["gas_used"],
                        contract_address=evidence["contract_address"],
                        chain_id=evidence["chain_id"],
                    )
                    st.success("Consent revoked on the local blockchain.")
                    show_chain_evidence(consent, revoked=True)


elif role == "Guardian":
    st.header("Multi-Party Guardian Approval")
    consent_id = st.text_input("Consent ID")
    consent = consent_db.get(consent_id) if consent_id else None

    if consent:
        evaluate_state(consent)
        st.write(
            f"Approvals: **{len(set(consent.signatures))}/{consent.threshold}** · "
            f"State: **{consent.state}**"
        )
        st.code(consent.consent_hash, language=None)
        guardian_did = st.selectbox("Guardian", consent.guardian_dids)

        if st.button("Approve Consent", type="primary"):
            if consent.revoked:
                st.error("A revoked consent cannot receive new approvals.")
            elif guardian_did in consent.signatures:
                st.warning("This guardian has already approved; duplicate approval was rejected.")
                audit_db.log(
                    actor_did=guardian_did,
                    actor_role="Guardian",
                    action="SIGN_CONSENT",
                    patient_did=consent.patient_did,
                    consent_id=consent.consent_id,
                    consent_hash=consent.consent_hash,
                    scope=consent.scope,
                    purpose=consent.purpose,
                    result="DENIED_DUPLICATE",
                )
            elif not verify_vc(guardian_did):
                st.error("Guardian DID/VC validation failed.")
            else:
                consent.signatures.append(guardian_did)
                evaluate_state(consent)
                consent_db.update(consent)
                audit_db.log(
                    actor_did=guardian_did,
                    actor_role="Guardian",
                    action="SIGN_CONSENT",
                    patient_did=consent.patient_did,
                    consent_id=consent.consent_id,
                    consent_hash=consent.consent_hash,
                    scope=consent.scope,
                    purpose=consent.purpose,
                    result="SUCCESS",
                    metadata={
                        "threshold": consent.threshold,
                        "signature_count": len(set(consent.signatures)),
                    },
                )
                st.success("Guardian approval recorded.")

                if len(set(consent.signatures)) >= consent.threshold and consent.token_id is None:
                    record_mint(consent)

        if len(set(consent.signatures)) >= consent.threshold and consent.token_id is None:
            st.warning("The threshold is complete, but the blockchain mint is still pending.")
            if st.button("Retry SBT Mint"):
                record_mint(consent)

        if consent.token_id is not None:
            show_chain_evidence(consent)
    elif consent_id:
        st.error("Consent ID was not found.")


elif role == "Doctor":
    st.header("Request Patient Data")
    consent_id = st.text_input("Consent ID")
    consent = consent_db.get(consent_id) if consent_id else None

    if consent:
        state = evaluate_state(consent)
        st.write(f"Consent State: **{state}**")
        st.write("Authorised Scope:", consent.scope)
        requested_scope = st.multiselect("Request Scope", consent.scope)
        show_chain_evidence(consent)

        if st.button("Access Patient Data", type="primary"):
            request = AccessRequest(
                consent.requester_did,
                consent.patient_did,
                requested_scope,
                consent.purpose,
                datetime.now(timezone.utc).isoformat(),
            )
            scope_valid = check_scope(consent, request)

            try:
                on_chain_valid = is_consent_valid_on_chain(consent)
                requester_authorised = has_requester_access_on_chain(consent)
            except BlockchainError as exc:
                on_chain_valid = False
                requester_authorised = False
                chain_error = str(exc)
            else:
                chain_error = None

            allowed = authorize(
                state=state,
                scope_valid=scope_valid,
                on_chain_valid=on_chain_valid,
                requester_authorised=requester_authorised,
            )

            audit_db.log(
                actor_did=consent.requester_did,
                actor_role="Doctor",
                action="DATA_ACCESS",
                patient_did=consent.patient_did,
                consent_id=consent.consent_id,
                consent_hash=consent.consent_hash,
                scope=requested_scope,
                purpose=consent.purpose,
                result="GRANTED" if allowed else "DENIED",
                token_id=consent.token_id,
                contract_address=consent.contract_address,
                chain_id=consent.chain_id,
                metadata={
                    "state": state,
                    "scope_valid": scope_valid,
                    "on_chain_valid": on_chain_valid,
                    "requester_authorised": requester_authorised,
                    "blockchain_error": chain_error,
                },
            )

            if allowed:
                st.success("Access Granted")
                data = repo.query_patient(consent.patient_did, requested_scope)
                for category, values in data.items():
                    st.subheader(category)
                    st.dataframe(values, use_container_width=True)
            else:
                st.error("Access Denied")
                st.json(
                    {
                        "state": state,
                        "scope_valid": scope_valid,
                        "on_chain_valid": on_chain_valid,
                        "requester_authorised": requester_authorised,
                        "blockchain_error": chain_error,
                    }
                )
    elif consent_id:
        st.error("Consent ID was not found.")


elif role == "Auditor":
    st.header("Audit Dashboard")

    if chain_status:
        st.subheader("Local Blockchain Status")
        st.json(chain_status)

    st.subheader("Consent Registry")
    consent_rows = []
    for consent in consent_db.all_consents():
        consent_rows.append(
            {
                "consent_id": consent.consent_id,
                "consent_hash": consent.consent_hash,
                "patient_did": consent.patient_did,
                "requester_did": consent.requester_did,
                "threshold": consent.threshold,
                "approval_count": len(set(consent.signatures)),
                "state": evaluate_state(consent),
                "token_id": consent.token_id,
                "contract_address": consent.contract_address,
                "mint_tx_hash": consent.mint_tx_hash,
                "mint_block_number": consent.mint_block_number,
                "mint_gas_used": consent.mint_gas_used,
                "revoke_tx_hash": consent.revoke_tx_hash,
                "revoke_block_number": consent.revoke_block_number,
                "revoke_gas_used": consent.revoke_gas_used,
            }
        )
    st.dataframe(pd.DataFrame(consent_rows), use_container_width=True)

    inspect_id = st.text_input("Inspect on-chain consent by Consent ID")
    inspected = consent_db.get(inspect_id) if inspect_id else None
    if inspected and inspected.token_id is not None:
        try:
            st.json(read_on_chain_consent(inspected))
        except BlockchainError as exc:
            st.error(str(exc))

    st.subheader("Audit Events")
    audit_frame = pd.DataFrame(audit_db.get())
    st.dataframe(audit_frame, use_container_width=True)
    if not audit_frame.empty:
        st.download_button(
            "Download Audit CSV",
            audit_frame.to_csv(index=False).encode("utf-8"),
            file_name="halah_audit.csv",
            mime="text/csv",
        )
