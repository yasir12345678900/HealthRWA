# HALAH: Blockchain Patient Consent Management

**HALAH — History Access Link for Authorised Healthcare** is a research proof of concept for multi-party and time-conditional patient consent. The current implementation runs on a **local Hardhat Ethereum-compatible blockchain** and does not require Mainnet, Sepolia, payment, or real cryptocurrency.

## Implemented proof-of-concept features

- Patient creates a consent record with a unique Consent ID and Keccak-256 consent hash.
- Two or more distinct guardian DIDs are required; duplicate approvals are rejected.
- The SBT is minted only when the configured approval threshold is satisfied.
- ERC-5484-style issuer-only burn authorisation and soulbound non-transferability.
- Unique token ID for each consent.
- `ConsentIssued` and `ConsentRevoked` smart-contract events.
- UTC `validFrom` and `validUntil` enforcement.
- Access denied before start, after expiry, and after revocation.
- Doctor access restricted to the healthcare data categories authorised by the patient.
- Audit evidence includes contract address, transaction hash, block number, gas used, chain ID, token ID, consent hash, and approval hash.
- Synthea patient data remains off-chain; only consent evidence is anchored locally.

## Architecture

```text
Patient / Guardians / Doctor / Auditor
                |
          Streamlit app
                |
             Web3.py
                |
    ConsentSBT smart contract
                |
     Local Hardhat chain 31337
```

## GitHub Codespaces

The dev-container configuration installs Python, Node.js, Hardhat, and project dependencies. It then starts the local Hardhat node, deploys `ConsentSBT`, and starts Streamlit.

For an existing Codespace that has not been rebuilt, run:

```bash
git pull --ff-only
npm install
bash .devcontainer/start-local-demo.sh
```

The forwarded ports are:

- `8501` — HALAH Streamlit application
- `8545` — Hardhat JSON-RPC

## Manual local startup

```bash
npm install
npm run compile
npm run test:contracts
```

Terminal 1:

```bash
npm run node
```

Terminal 2:

```bash
npm run deploy:local
pip install -r requirements.txt
streamlit run app.py
```

## Automated validation

GitHub Actions performs:

1. Solidity compilation.
2. Smart-contract unit tests.
3. An end-to-end deploy, mint, access-check, and revoke scenario.
4. A persistent local Hardhat deployment.
5. Python Web3 integration testing.
6. Streamlit startup and health verification.
7. Upload of blockchain evidence as a workflow artifact.

## Key files

```text
blockchain/contracts/ConsentSBT.sol       Smart contract
blockchain/contract.py                    Web3.py adapter
blockchain/scripts/deploy.js              Local deployment
blockchain/scripts/e2e-demo.js            Transaction evidence scenario
blockchain/test/ConsentSBT.test.js         Contract tests
services/blockchain_service.py            Application-chain integration
services/consent_service.py               Canonical consent and approval hashes
app.py                                    Streamlit workflow
```

## Research limitations

- This is a proof of concept, not a production healthcare system.
- The local blockchain resets when the Hardhat node is restarted.
- DID/VC checks are currently demonstrative identifier checks rather than full credential-signature verification.
- Privacy-preserving enforcement such as Zero-Knowledge Proofs is reserved for the subsequent research stage.
- No clinical data is written to the blockchain.

## Authors

Charles, Yasir, Daniel, Kejia, Yasmin, and Farookh.
