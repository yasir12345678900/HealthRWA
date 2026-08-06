const { expect } = require("chai");
const { ethers } = require("hardhat");

async function latestTimestamp() {
  const block = await ethers.provider.getBlock("latest");
  return block.timestamp;
}

describe("ConsentSBT", function () {
  async function deployFixture() {
    const [owner, patient, requester, other] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("ConsentSBT");
    const contract = await Factory.deploy();
    await contract.waitForDeployment();
    return { contract, owner, patient, requester, other };
  }

  it("mints a unique time-bound consent SBT and emits ConsentIssued", async function () {
    const { contract, patient, requester } = await deployFixture();
    const now = await latestTimestamp();
    const consentHash = ethers.keccak256(ethers.toUtf8Bytes("consent-001"));

    await expect(
      contract.mintConsent(
        patient.address,
        requester.address,
        consentHash,
        "Treatment",
        now,
        now + 3600
      )
    )
      .to.emit(contract, "ConsentIssued")
      .withArgs(
        1,
        consentHash,
        patient.address,
        requester.address,
        now,
        now + 3600
      );

    expect(await contract.ownerOf(1)).to.equal(patient.address);
    expect(await contract.tokenByConsentHash(consentHash)).to.equal(1);
    expect(await contract.checkAccess(1, requester.address)).to.equal(true);
  });

  it("rejects duplicate consent hashes", async function () {
    const { contract, patient, requester } = await deployFixture();
    const now = await latestTimestamp();
    const consentHash = ethers.keccak256(ethers.toUtf8Bytes("same-consent"));

    await contract.mintConsent(
      patient.address,
      requester.address,
      consentHash,
      "Treatment",
      now,
      now + 3600
    );

    await expect(
      contract.mintConsent(
        patient.address,
        requester.address,
        consentHash,
        "Treatment",
        now,
        now + 7200
      )
    ).to.be.revertedWith("Consent already minted");
  });

  it("is non-transferable", async function () {
    const { contract, patient, requester, other } = await deployFixture();
    const now = await latestTimestamp();
    const consentHash = ethers.keccak256(ethers.toUtf8Bytes("consent-002"));

    await contract.mintConsent(
      patient.address,
      requester.address,
      consentHash,
      "Treatment",
      now,
      now + 3600
    );

    await expect(
      contract
        .connect(patient)
        .transferFrom(patient.address, other.address, 1)
    ).to.be.revertedWith("Soulbound token");
  });

  it("denies access after revocation", async function () {
    const { contract, patient, requester } = await deployFixture();
    const now = await latestTimestamp();
    const consentHash = ethers.keccak256(ethers.toUtf8Bytes("consent-003"));

    await contract.mintConsent(
      patient.address,
      requester.address,
      consentHash,
      "Treatment",
      now,
      now + 3600
    );

    await expect(contract.revoke(1))
      .to.emit(contract, "ConsentRevoked")
      .withArgs(1, consentHash, anyValue);

    expect(await contract.checkValid(1)).to.equal(false);
  });

  it("denies access before validFrom and after validUntil", async function () {
    const { contract, patient, requester } = await deployFixture();
    const now = await latestTimestamp();
    const consentHash = ethers.keccak256(ethers.toUtf8Bytes("consent-004"));

    await contract.mintConsent(
      patient.address,
      requester.address,
      consentHash,
      "Treatment",
      now + 100,
      now + 200
    );

    expect(await contract.checkValid(1)).to.equal(false);

    await ethers.provider.send("evm_setNextBlockTimestamp", [now + 150]);
    await ethers.provider.send("evm_mine", []);
    expect(await contract.checkValid(1)).to.equal(true);

    await ethers.provider.send("evm_setNextBlockTimestamp", [now + 201]);
    await ethers.provider.send("evm_mine", []);
    expect(await contract.checkValid(1)).to.equal(false);
  });
});

const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");
