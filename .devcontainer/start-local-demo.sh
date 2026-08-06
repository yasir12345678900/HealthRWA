#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
mkdir -p .logs

if [ ! -x node_modules/.bin/hardhat ]; then
  echo "Installing Hardhat dependencies..."
  npm install
fi

npm run compile

rpc_ready() {
  curl --silent --fail \
    --header 'Content-Type: application/json' \
    --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
    http://127.0.0.1:8545 > /dev/null
}

if ! rpc_ready; then
  echo "Starting local Hardhat node on chain ID 31337..."
  nohup npm run node > .logs/hardhat-node.log 2>&1 &
  for attempt in {1..30}; do
    if rpc_ready; then
      break
    fi
    sleep 1
  done
fi

if ! rpc_ready; then
  echo "Hardhat node failed to start."
  cat .logs/hardhat-node.log || true
  exit 1
fi

echo "Deploying ConsentSBT to the local Hardhat node..."
npm run deploy:local | tee .logs/deploy.log

pkill -f "streamlit run app.py" 2>/dev/null || true

echo "Starting HALAH Streamlit application..."
exec streamlit run app.py \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --server.port 8501
