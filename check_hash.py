from web3 import Web3
from dotenv import load_dotenv
import json, os

load_dotenv("contract/.env")
RPC_URL = os.getenv("RPC_URL")
print("RPC_URL loaded as:", RPC_URL)

w3 = Web3(Web3.HTTPProvider(RPC_URL))

with open("contract/contract_abi.json") as f:
    abi = json.load(f)

contract = w3.eth.contract(address="0x7784DF12C4B9Ce810f73dceE1Be194Fae9472217", abi=abi)

wallet1 = "0x5df30d270De7F2bc60c2cac2A91e1E4f82266654"
wallet2 = "0x45837d20c6B6D996df1C87E1cb4A1D6c3192E0E4"

hash1 = contract.functions.name_hash(Web3.to_checksum_address(wallet1)).call()
hash2 = contract.functions.name_hash(Web3.to_checksum_address(wallet2)).call()

print("Wallet 1 name_hash:", hash1.hex())
print("Wallet 2 name_hash:", hash2.hex())
print("Different?", hash1 != hash2)