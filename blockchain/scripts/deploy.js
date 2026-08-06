const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
  const ConsentSBT = await hre.ethers.getContractFactory("ConsentSBT");
  const contract = await ConsentSBT.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  const network = await hre.ethers.provider.getNetwork();

  const deployment = {
    contractAddress: address,
    chainId: Number(network.chainId),
    deployedAt: new Date().toISOString()
  };

  const outputDir = path.join(__dirname, "..", "deployment");
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(
    path.join(outputDir, "local.json"),
    JSON.stringify(deployment, null, 2)
  );

  console.log("ConsentSBT deployed:", address);
  console.log("Chain ID:", network.chainId.toString());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
