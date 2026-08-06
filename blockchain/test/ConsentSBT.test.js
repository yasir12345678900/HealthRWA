const { expect } = require("chai");
const { ethers } = require("hardhat");
const {
  anyValue
} = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

async function latestTimestamp() {
  const block = await ethers.provider.getBlock("latest");
  return block.timestamp;
}

function hashes(label) {
  return {
    consentHash: ethers.keccak256(ethers.toUtf8Bytes(`consent:${label}`)),
    approvalHash: ethers.keccak256(ethers.toUtf8Bytes(`approvals:${label}`))
  };
}

describe("ConsentSBT", function () {
  async function deployFixture() {
    const [owner, patient, requester, other] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("ConsentSBT");
    const contract = await Factory.deploy();
    await contract.waitForDeployment();
    return { contract, owner, patient, requester, other };
  }

  async function mintDefault(contract, patient, requester, label = "001") {
    const now = await latestTimestamp();
    const { consentHash, approvalHash } = hashes(label);
    const tx = await contract.mintConsent(
      patient.address,
      requester.address,
      consentHash,
      approvalHash,
      "Treatment",
      now,
      now + 3600,
      2,
      2
    );
    await tx.wait();
    return { now, consentHash, approvalHash };
  }

  it("mints a unique threshold-approved ERC-5484-style consent SBT", async function () {
    const { contract, patient, requester } = await deployFixture();
    const now = await latestTimestamp();
    const { consentHash, approvalHash } = hashes("issued");

    await expect(
      contract.mintConsent(
        patient.address,
        requester.address,
        consentHash,
        approvalHash,
        "Treatment",
        now,
        now + 3600,
        2,
        2
      )
    )
      .to.emit(contract, "ConsentIssued")
      .withArgs(
        1,
        consentHash,
        approvalHash,
        patient.address,
        requester.address,
        now,
        now + 3600,
        2,
        2
      );

    expect(await contract.ownerOf(1)).to.equal(patient.address);
    expect(await contract.tokenByConsentHash(consentHash)).to.equal(1);
    expect(await contract.checkAccess(1, requester.address)).to.equal(true);
    expect(await contract.burnAuth(1)).to.equal(0); // IssuerOnly
  });

  it("rejects minting when the multi-party threshold is not met", async function () {
    const { contract, patient, requester } = await deployFixture();
    const now = await latestTimestamp();
    const { consentHash, approvalHash } = hashes("insufficient");

    await expect(
      contract.mintConsent(
        patient.address,
        requester.address,
        consentHash,
        approvalHash,
        "Treatment",
        now,
        now + 3600,
        2,
        1
      )
    ).to.be.revertedWith("Insufficient approvals");
  });

  it("rejects duplicate consent hashes", async function () {
    const { contract, patient, requester } = await deployFixture();
    const now = await latestTimestamp();
    const { consentHash, approvalHash } = hashes("duplicate");

    await contract.mintConsent(
      patient.address,
      requester.address,
      consentHash,
      approvalHash,
      "Treatment",
      now,
      now + 3600,
      2,
      2
    );

    await expect(
      contract.mintConsent(
        patient.address,
        requester.address,
        consentHash,
        ethers.keccak256(ethers.toUtf8Bytes("other-approvals")),
        "Treatment",
        now,
        now + 7200,
        2,
        2
      )
    ).to.be.revertedWith("Consent already minted");
  });

  it("is soulbound and rejects transfer approvals", async function () {
    const { contract, patient, requester, other } = await deployFixture();
    await mintDefault(contract, patient, requester, "soulbound");

    await expect(
      contract.connect(patient).transferFrom(patient.address, other.address, 1)
    ).to.be.revertedWith("Soulbound token");

    await expect(
      contract.connect(patient).approve(other.address, 1)
    ).to.be.revertedWith("Soulbound token");
  });

  it("denies access after issuer revocation and emits ConsentRevoked", async function () {
    const { contract, patient, requester } = await deployFixture();
    const { consentHash } = await mintDefault(
      contract,
      patient,
      requester,
      "revocation"
    );

    await expect(contract.revoke(1))
      .to.emit(contract, "ConsentRevoked")
      .withArgs(1, consentHash, anyValue);

    expect(await contract.checkValid(1)).to.equal(false);
    expect(await contract.checkAccess(1, requester.address)).to.equal(false);
  });

  it("denies access before validFrom and after validUntil", async function () {
    const { contract, patient, requester } = await deployFixture();
    const now = await latestTimestamp();
    const { consentHash, approvalHash } = hashes("time-window");

    await contract.mintConsent(
      patient.address,
      requester.address,
      consentHash,
      approvalHash,
      "Treatment",
      now + 100,
      now + 200,
      2,
      2
    );

    expect(await contract.checkValid(1)).to.equal(false);

    await ethers.provider.send("evm_setNextBlockTimestamp", [now + 150]);
    await ethers.provider.send("evm_mine", []);
    expect(await contract.checkValid(1)).to.equal(true);

    await ethers.provider.send("evm_setNextBlockTimestamp", [now + 201]);
    await ethers.provider.send("evm_mine", []);
    expect(await contract.checkValid(1)).to.equal(false);
  });

  it("denies an address that is not the authorised requester", async function () {
    const { contract, patient, requester, other } = await deployFixture();
    await mintDefault(contract, patient, requester, "requester");

    expect(await contract.checkAccess(1, requester.address)).to.equal(true);
    expect(await contract.checkAccess(1, other.address)).to.equal(false);
  });
});
