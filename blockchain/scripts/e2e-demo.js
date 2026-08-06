const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

function findEvent(contract, receipt, name) {
  for (const log of receipt.logs) {
    try {
      const parsed = contract.interface.parseLog(log);
      if (parsed && parsed.name === name) return parsed;
    } catch (_) {}
  }
  throw new Error(`${name} was not emitted`);
}

async function main() {
  const [owner, patient, requester] = await hre.ethers.getSigners();
  const Factory = await hre.ethers.getContractFactory("ConsentSBT");
  const contract = await Factory.deploy();
  const deployReceipt = await contract.deploymentTransaction().wait();
  await contract.waitForDeployment();

  const block = await hre.ethers.provider.getBlock("latest");
  const consentHash = hre.ethers.keccak256(
    hre.ethers.toUtf8Bytes("HALAH-CI-CONSENT-001")
  );
  const approvalHash = hre.ethers.keccak256(
    hre.ethers.toUtf8Bytes("did:parent:A|did:parent:B")
  );

  const mintTx = await contract.mintConsent(
    patient.address,
    requester.address,
    consentHash,
    approvalHash,
    "Treatment",
    block.timestamp,
    block.timestamp + 3600,
    2,
    2
  );
  const mintReceipt = await mintTx.wait();
  const issued = findEvent(contract, mintReceipt, "ConsentIssued");
  const tokenId = Number(issued.args.tokenId);

  const validBefore = await contract.checkValid(tokenId);
  const accessBefore = await contract.checkAccess(tokenId, requester.address);

  const revokeTx = await contract.revoke(tokenId);
  const revokeReceipt = await revokeTx.wait();
  findEvent(contract, revokeReceipt, "ConsentRevoked");
  const validAfter = await contract.checkValid(tokenId);

  const network = await hre.ethers.provider.getNetwork();
  const evidence = {
    generatedAt: new Date().toISOString(),
    chainId: Number(network.chainId),
    contractAddress: await contract.getAddress(),
    ownerAddress: owner.address,
    deployTxHash: deployReceipt.hash,
    deployBlockNumber: deployReceipt.blockNumber,
    deployGasUsed: deployReceipt.gasUsed.toString(),
    consentHash,
    approvalHash,
    tokenId,
    patientAddress: patient.address,
    requesterAddress: requester.address,
    mintTxHash: mintReceipt.hash,
    mintBlockNumber: mintReceipt.blockNumber,
    mintGasUsed: mintReceipt.gasUsed.toString(),
    validBefore,
    accessBefore,
    revokeTxHash: revokeReceipt.hash,
    revokeBlockNumber: revokeReceipt.blockNumber,
    revokeGasUsed: revokeReceipt.gasUsed.toString(),
    validAfter
  };

  const outputDir = path.join(__dirname, "..", "evidence");
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(
    path.join(outputDir, "e2e-local-hardhat.json"),
    JSON.stringify(evidence, null, 2)
  );
  console.log(JSON.stringify(evidence, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
