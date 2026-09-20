"""
Digital Passport - Web Edition (Tuakiri Travelers Permit)
======================================================

Flask backend for the browser version. Reuses the same OCR / mock-KYC
logic as the original customtkinter version, plus:

    - The wallet address is filled in by the user's own MetaMask wallet
      (connected client-side in the browser), not typed manually.
    - The ID photo is uploaded through a normal HTML file input.
    - Verification (OCR + name matching) runs here on the server and
      returns JSON for the page to render (seal stamp, MRZ line, etc).
    - The actual on-chain write (a hash anchor + access grants) is done
      from the BROWSER using ethers.js, signed by the user's own wallet
      via MetaMask - no private key is ever stored on the server.

Privacy model:
    - The real name is stored HERE, off-chain, encrypted at rest.
    - The Identity Registry smart contract stores only a hash of the
      name (for tamper-evidence) plus an access-control list of which
      viewer addresses each owner has granted permission to.
    - Before returning a stored name to anyone, this server checks the
      on-chain `access` mapping before returning anything. The blockchain is the
      tamper-proof source of truth for permissions; this server just
      enforces what it says.

Run with:
    py -m pip install flask pytesseract pillow web3 cryptography
    py app.py

Then open http://127.0.0.1:5000 in a browser with MetaMask installed.
"""

import json
import os
import string
import sys
import io
import threading
import webbrowser

from eth_account import Account
from eth_account.messages import encode_defunct
from cryptography.fernet import Fernet
from flask import Flask, render_template, request, jsonify
from PIL import Image
import pytesseract
from web3 import Web3

app = Flask(__name__)

# ----------------------------------------------------------------------
# OCR engine setup
# ----------------------------------------------------------------------
if sys.platform.startswith("win"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ----------------------------------------------------------------------
# Blockchain connection setup
# ----------------------------------------------------------------------
RPC_URL = "https://liteforge.rpc.caldera.xyz/http"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# TODO: fill these in after running contract/deploy.py
CONTRACT_ADDRESS = "0x91fD97086d24234D8f124388d66A89006af201A5"
CONTRACT_ABI = None      # Keep None as python will Auto-load the ABI from contract/contract_abi.json

# Auto-load the ABI from contract/contract_abi.json if it's been generated,
# so you only have to set CONTRACT_ADDRESS by hand.
_abi_path = os.path.join(os.path.dirname(__file__), "contract", "contract_abi.json")
if CONTRACT_ABI is None and os.path.exists(_abi_path):
    with open(_abi_path) as f:
        CONTRACT_ABI = json.load(f)

contract = None
if CONTRACT_ADDRESS and CONTRACT_ABI:
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)


# ----------------------------------------------------------------------
# Encrypted off-chain storage
# ----------------------------------------------------------------------
# NOTE: this is a simple local JSON "database" for hackathon purposes.
# A real deployment would use a proper database, and manage the
# encryption key via a secrets manager rather than a local file.
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
KEY_PATH = os.path.join(DATA_DIR, "secret.key")
STORE_PATH = os.path.join(DATA_DIR, "identities.json")

if os.path.exists(KEY_PATH):
    with open(KEY_PATH, "rb") as f:
        _encryption_key = f.read()
else:
    _encryption_key = Fernet.generate_key()
    with open(KEY_PATH, "wb") as f:
        f.write(_encryption_key)

fernet = Fernet(_encryption_key)


def _load_store():
    if not os.path.exists(STORE_PATH):
        return {}
    with open(STORE_PATH) as f:
        return json.load(f)


def _save_store(store):
    with open(STORE_PATH, "w") as f:
        json.dump(store, f, indent=2)


def store_name(address, name):
    """Encrypt and save a name against a wallet address (overwrites any previous entry)."""
    store = _load_store()
    encrypted = fernet.encrypt(name.encode()).decode()
    store[address] = encrypted
    _save_store(store)


def get_name(address):
    """Decrypt and return the stored name for an address, or None if not registered."""
    store = _load_store()
    encrypted = store.get(address)
    if not encrypted:
        return None
    return fernet.decrypt(encrypted.encode()).decode()


# ----------------------------------------------------------------------
# Mock election storage
# ----------------------------------------------------------------------
# Demonstrates gating a real-world action (voting) behind on-chain
# identity verification: only wallets registered in the Identity
# Registry contract are allowed to cast a vote, and each verified
# identity gets exactly one vote.
VOTE_OPTIONS = ["Kiwi", "Tuatara", "Kea"]
VOTES_PATH = os.path.join(DATA_DIR, "votes.json")


def _load_votes():
    if not os.path.exists(VOTES_PATH):
        return {"tally": {option: 0 for option in VOTE_OPTIONS}, "voted": []}
    with open(VOTES_PATH) as f:
        return json.load(f)


def _save_votes(votes):
    with open(VOTES_PATH, "w") as f:
        json.dump(votes, f, indent=2)


def is_identity_verified(address):
    """True if this address has completed ID registration on-chain."""
    if contract is None:
        return False
    return contract.functions.registered(address).call()


# ----------------------------------------------------------------------
# Text processing (same logic as the desktop version)
# ----------------------------------------------------------------------
def clean_text(text_str):
    """Remove punctuation, digits, and newlines from OCR output; lowercase the result."""
    text_str = text_str.replace("\n", " ").replace("\r", " ")
    text_str = text_str.translate(str.maketrans("", "", string.punctuation))
    text_str = text_str.translate(str.maketrans("", "", string.digits))
    text_str = " ".join(text_str.split())
    return text_str.lower()


def extract_text_from_image(file_stream):
    """Run OCR on an in-memory uploaded image and return the raw extracted text."""
    image = Image.open(file_stream)
    return pytesseract.image_to_string(image)


def generate_mrz(name, address):
    """
    Build a passport-style two-line Machine Readable Zone from the
    name and wallet address. Purely cosmetic - not a real MRZ standard.
    """
    parts = [p for p in name.upper().split() if p]
    if len(parts) >= 2:
        surname, given = parts[-1], "<".join(parts[:-1])
    elif parts:
        surname, given = parts[0], ""
    else:
        surname, given = "UNKNOWN", ""

    line1 = f"P<ETH{surname}<<{given}"
    line1 = (line1 + "<" * 44)[:44]

    addr_body = address[2:] if address.lower().startswith("0x") else address
    line2 = ("ETH" + addr_body.upper() + "<" * 44)[:44]

    return line1, line2


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/vote")
def vote_page():
    return render_template("vote.html")


@app.route("/api/vote-status", methods=["GET"])
def vote_status():
    """
    Query params:
        address - the connected wallet checking its own voting eligibility

    Returns JSON:
        { ok, error, registered, already_voted, options, tally }
    """
    address = request.args.get("address", "").strip()

    if not Web3.is_address(address):
        return jsonify(ok=False, error="Invalid wallet address."), 400

    address = Web3.to_checksum_address(address)

    if contract is None:
        return jsonify(
            ok=False,
            error="Contract not configured yet - set CONTRACT_ADDRESS in app.py.",
        ), 500

    votes = _load_votes()

    return jsonify(
        ok=True,
        registered=is_identity_verified(address),
        already_voted=address in votes["voted"],
        options=VOTE_OPTIONS,
        tally=votes["tally"],
    )


@app.route("/api/vote", methods=["POST"])
def cast_vote():
    """
    JSON body:
        address - the connected wallet casting the vote
        option  - one of VOTE_OPTIONS

    Verifies on-chain identity registration and that this address
    hasn't already voted, before recording the vote.

    Returns JSON:
        { ok, error, tally }
    """
    body = request.get_json(silent=True) or {}
    address = body.get("address", "").strip()
    option = body.get("option", "").strip()
    message = body.get("message", "")
    signature = body.get("signature", "")

    expected_message = f"MANA DID Vote\nAddress: {address}\nOption: {option}"
    if message != expected_message:
        return jsonify(ok=False, error="Signed message doesn't match vote request."), 400

    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    except Exception:
        return jsonify(ok=False, error="Invalid signature."), 401

    if recovered.lower() != address.lower():
        return jsonify(ok=False, error="Signature does not match the claimed wallet."), 401

    if not Web3.is_address(address):
        return jsonify(ok=False, error="Invalid wallet address."), 400

    if option not in VOTE_OPTIONS:
        return jsonify(ok=False, error="Not a valid voting option."), 400

    address = Web3.to_checksum_address(address)

    if contract is None:
        return jsonify(
            ok=False,
            error="Contract not configured yet - set CONTRACT_ADDRESS in app.py.",
        ), 500

    if not is_identity_verified(address):
        return jsonify(
            ok=False, error="This wallet hasn't completed identity verification yet."
        ), 403

    votes = _load_votes()

    if address in votes["voted"]:
        return jsonify(ok=False, error="This identity has already voted.", tally=votes["tally"]), 409

    votes["tally"][option] += 1
    votes["voted"].append(address)
    _save_votes(votes)

    return jsonify(ok=True, tally=votes["tally"])


@app.route("/api/vote-results", methods=["GET"])
def vote_results():
    """Public tally - no identity check needed to view results."""
    votes = _load_votes()
    return jsonify(ok=True, options=VOTE_OPTIONS, tally=votes["tally"])


@app.route("/verify", methods=["POST"])
def verify():
    """
    Accepts multipart form data:
        name        - the typed full name
        address     - the connected wallet address (from MetaMask)
        id_image    - the uploaded ID photo file

    On a successful OCR name match, encrypts and stores the name
    off-chain (keyed by wallet address) and returns the MRZ line for
    display. The frontend separately writes the name's hash on-chain
    once this returns ok=True.

    Returns JSON:
        { ok, error, cleaned_text, mrz_line1, mrz_line2, address }
    """
    name = request.form.get("name", "").strip()
    address = request.form.get("address", "").strip()
    image_file = request.files.get("id_image")

    if not name:
        return jsonify(ok=False, error="Enter a name to continue."), 400

    if not Web3.is_address(address):
        return jsonify(ok=False, error="Connect a valid wallet first."), 400

    if not image_file:
        return jsonify(ok=False, error="Upload an ID photo first."), 400

    checksum_address = Web3.to_checksum_address(address)

    raw_text = extract_text_from_image(io.BytesIO(image_file.read()))
    cleaned = clean_text(raw_text)

    if clean_text(name) not in cleaned:
        return jsonify(
            ok=False, error="Name doesn't match the text on the ID.", cleaned_text=cleaned
        ), 200

    # store the real name off-chain, encrypted at rest
    store_name(checksum_address, name)

    line1, line2 = generate_mrz(name, checksum_address)

    return jsonify(
        ok=True,
        cleaned_text=cleaned,
        mrz_line1=line1,
        mrz_line2=line2,
        address=checksum_address,
    )


@app.route("/lookup", methods=["GET"])
def lookup():
    """
    Query params:
        owner   - the wallet address whose name is being requested
        viewer  - the wallet address making the request

    Checks the on-chain access list before returning anything. The
    owner always has access to their own record.

    Returns JSON:
        { ok, error, name }
    """
    owner = request.args.get("owner", "").strip()
    viewer = request.args.get("viewer", "").strip()

    if not Web3.is_address(owner) or not Web3.is_address(viewer):
        return jsonify(ok=False, error="Invalid wallet address."), 400

    owner = Web3.to_checksum_address(owner)
    viewer = Web3.to_checksum_address(viewer)

    if contract is None:
        return jsonify(
            ok=False,
            error="Contract not configured yet - set CONTRACT_ADDRESS in app.py.",
        ), 500

    # NOTE: we deliberately call the raw `access` mapping getter here
    # instead of the contract's `has_access` convenience function.
    # `has_access` always returns True when owner == viewer (so an owner
    # can always see their own record) - but that auto-allow isn't
    # something we want the general lookup tool to rely on here, and a
    # deployed contract's code can't be edited after the fact, so we
    # enforce "explicit grants only" at this layer instead.
    allowed = contract.functions.access(owner, viewer).call()
    if not allowed:
        return jsonify(ok=False, error="ID access not provided for this wallet."), 403

    name = get_name(owner)
    if name is None:
        return jsonify(ok=False, error="No identity registered for that address."), 404

    return jsonify(ok=True, name=name)


def _open_browser_tabs():
    """Open the Register and Mock Election pages in separate tabs once the server is up."""
    webbrowser.open_new("http://127.0.0.1:5000/")
    webbrowser.open_new_tab("http://127.0.0.1:5000/vote")


if __name__ == "__main__":
    # Flask's debug reloader runs this file twice (a parent watcher process
    # and a child that actually serves requests). Only the child sets
    # WERKZEUG_RUN_MAIN, so this guard stops the tabs from opening twice.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.25, _open_browser_tabs).start()

    app.run(debug=True)