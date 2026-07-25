"""
Deploy the Tuakiri Identity Registry contract to Sepolia testnet.

Setup:
    py -m pip install vyper web3 python-dotenv

    Create a .env file next to this script containing:
        RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_ALCHEMY_KEY
        DEPLOYER_PRIVATE_KEY=your_testnet_wallet_private_key

    IMPORTANT: use a fresh TESTNET-ONLY wallet for DEPLOYER_PRIVATE_KEY.
    Never put a real/mainnet wallet's private key in a file. In MetaMask:
    create a new account, switch to Sepolia, get free testnet ETH from
    a faucet (search "Sepolia faucet"), then export that account's key
    (Account details -> Show private key) and use it here.

Run:
    py deploy.py

This prints the deployed contract address and writes contract_abi.json,
which app.py needs to talk to the contract.
"""

import json
import os

from dotenv import load_dotenv
from vyper import compile_code
from web3 import Web3

load_dotenv()

RPC_URL = os.environ["RPC_URL"]
PRIVATE_KEY = os.environ["DEPLOYER_PRIVATE_KEY"]

CONTRACT_PATH = os.path.join(os.path.dirname(__file__), "identity_registry.vy")

with open(CONTRACT_PATH) as f:
    source = f.read()

print("Compiling contract...")
compiled = compile_code(source, output_formats=["abi", "bytecode"])
abi = compiled["abi"]
bytecode = compiled["bytecode"]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)

print(f"Deploying from {account.address} ...")

ContractFactory = w3.eth.contract(abi=abi, bytecode=bytecode)

tx = ContractFactory.constructor().build_transaction({
    "from": account.address,
    "nonce": w3.eth.get_transaction_count(account.address),
    "gas": 1_500_000,
    "gasPrice": w3.eth.gas_price,
})
signed = account.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print("Transaction sent, waiting for confirmation...")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
contract_address = receipt.contractAddress

print(f"\nContract deployed at: {contract_address}")

abi_path = os.path.join(os.path.dirname(__file__), "contract_abi.json")
with open(abi_path, "w") as f:
    json.dump(abi, f, indent=2)

print(f"ABI saved to {abi_path}")
print("\nNext step: copy the contract address and the contents of")
print("contract_abi.json into app.py (CONTRACT_ADDRESS / CONTRACT_ABI)")
print("and into static/script.js (CONTRACT_ADDRESS / CONTRACT_ABI).")
