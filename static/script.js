// Digital Passport - frontend logic
// Handles: connecting MetaMask, previewing the uploaded ID photo,
// calling the Flask /verify endpoint, writing the identity hash +
// access grants on-chain (signed by the user's own wallet), and
// looking up records via the backend (which checks on-chain permission
// before returning anything).

// TODO: fill these in after running contract/deploy.py
const CONTRACT_ADDRESS = "0x91fD97086d24234D8f124388d66A89006af201A5";
const CONTRACT_ABI = [
  {
    "name": "Registered",
    "inputs": [
      {
        "name": "owner",
        "type": "address",
        "indexed": false
      }
    ],
    "anonymous": false,
    "type": "event"
  },
  {
    "name": "AccessGranted",
    "inputs": [
      {
        "name": "owner",
        "type": "address",
        "indexed": false
      },
      {
        "name": "viewer",
        "type": "address",
        "indexed": false
      }
    ],
    "anonymous": false,
    "type": "event"
  },
  {
    "name": "AccessRevoked",
    "inputs": [
      {
        "name": "owner",
        "type": "address",
        "indexed": false
      },
      {
        "name": "viewer",
        "type": "address",
        "indexed": false
      }
    ],
    "anonymous": false,
    "type": "event"
  },
  {
    "stateMutability": "nonpayable",
    "type": "function",
    "name": "register",
    "inputs": [
      {
        "name": "hashed_name",
        "type": "bytes32"
      }
    ],
    "outputs": []
  },
  {
    "stateMutability": "nonpayable",
    "type": "function",
    "name": "grant_access",
    "inputs": [
      {
        "name": "viewer",
        "type": "address"
      }
    ],
    "outputs": []
  },
  {
    "stateMutability": "nonpayable",
    "type": "function",
    "name": "revoke_access",
    "inputs": [
      {
        "name": "viewer",
        "type": "address"
      }
    ],
    "outputs": []
  },
  {
    "stateMutability": "view",
    "type": "function",
    "name": "has_access",
    "inputs": [
      {
        "name": "owner",
        "type": "address"
      },
      {
        "name": "viewer",
        "type": "address"
      }
    ],
    "outputs": [
      {
        "name": "",
        "type": "bool"
      }
    ]
  },
  {
    "stateMutability": "view",
    "type": "function",
    "name": "registered",
    "inputs": [
      {
        "name": "arg0",
        "type": "address"
      }
    ],
    "outputs": [
      {
        "name": "",
        "type": "bool"
      }
    ]
  },
  {
    "stateMutability": "view",
    "type": "function",
    "name": "name_hash",
    "inputs": [
      {
        "name": "arg0",
        "type": "address"
      }
    ],
    "outputs": [
      {
        "name": "",
        "type": "bytes32"
      }
    ]
  },
  {
    "stateMutability": "view",
    "type": "function",
    "name": "access",
    "inputs": [
      {
        "name": "arg0",
        "type": "address"
      },
      {
        "name": "arg1",
        "type": "address"
      }
    ],
    "outputs": [
      {
        "name": "",
        "type": "bool"
      }
    ]
  }
];

let connectedAddress = null;
let selectedFile = null;

const connectBtn = document.getElementById("connect-btn");
const walletDisplay = document.getElementById("wallet-display");
const photoInput = document.getElementById("id-photo");
const photoPreview = document.getElementById("photo-preview");
const photoPlaceholder = document.getElementById("photo-placeholder");
const uploadStatus = document.getElementById("upload-status");
const verifyBtn = document.getElementById("verify-btn");
const resultText = document.getElementById("result-text");
const spinner = document.getElementById("spinner-row");
const spinnerLabel = document.querySelector("#spinner-row .spinner-label");
const mrzEl = document.getElementById("mrz");
const sealEl = document.getElementById("seal");
const nameInput = document.getElementById("name");

const grantAddressInput = document.getElementById("grant-address");
const grantBtn = document.getElementById("grant-btn");
const revokeBtn = document.getElementById("revoke-btn");
const accessStatus = document.getElementById("access-status");

const lookupAddressInput = document.getElementById("lookup-address");
const lookupBtn = document.getElementById("lookup-btn");
const lookupStatus = document.getElementById("lookup-status");

// ---------------- Contract helper ----------------
async function getContractWithSigner() {
  const provider = new ethers.BrowserProvider(window.ethereum);
  const signer = await provider.getSigner();
  return new ethers.Contract(CONTRACT_ADDRESS, CONTRACT_ABI, signer);
}

// ---------------- Wallet connection ----------------
connectBtn.addEventListener("click", async () => {
  if (!window.ethereum) {
    walletDisplay.value = "MetaMask not found";
    return;
  }

  try {
    const provider = new ethers.BrowserProvider(window.ethereum);
    const accounts = await provider.send("eth_requestAccounts", []);
    connectedAddress = accounts[0];
    walletDisplay.value = connectedAddress;
    connectBtn.textContent = "Connected";
  } catch (err) {
    console.error(err);
    walletDisplay.value = "Connection rejected";
  }
});

// ---------------- Photo upload + preview ----------------
photoInput.addEventListener("change", () => {
  const file = photoInput.files[0];
  if (!file) return;

  selectedFile = file;
  const objectUrl = URL.createObjectURL(file);
  photoPreview.src = objectUrl;
  photoPreview.hidden = false;
  photoPlaceholder.hidden = true;

  uploadStatus.textContent = "ID received";
  uploadStatus.className = "status-text ok";

  // reset any previous verification visuals
  sealEl.classList.remove("show");
  mrzEl.textContent = "";
  resultText.textContent = "";
});

// ---------------- Verify & Register ----------------
verifyBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();

  if (!name) {
    showResult("Enter a name to continue.", "error");
    return;
  }
  if (!connectedAddress) {
    showResult("Connect your wallet first.", "error");
    return;
  }
  if (!selectedFile) {
    showResult("Upload an ID photo first.", "error");
    return;
  }

  verifyBtn.textContent = "Checking...";
  verifyBtn.disabled = true;
  spinner.classList.add("show");
  resultText.textContent = "";

  const MIN_SPINNER_MS = 2500;
  const startTime = Date.now();

  const formData = new FormData();
  formData.append("name", name);
  formData.append("address", connectedAddress);
  formData.append("id_image", selectedFile);

  try {
    const response = await fetch("/verify", { method: "POST", body: formData });
    const data = await response.json();

    // keep the spinner visible for at least MIN_SPINNER_MS, even if the
    // server answered faster than that
    const elapsed = Date.now() - startTime;
    if (elapsed < MIN_SPINNER_MS) {
      await new Promise((resolve) => setTimeout(resolve, MIN_SPINNER_MS - elapsed));
    }

    if (!data.ok) {
      showResult(data.error || "Verification failed.", "error");
      return;
    }

    showResult(`Verified. Confirm the transaction in MetaMask to register on-chain...`, "ok");
    mrzEl.textContent = `${data.mrz_line1}\n${data.mrz_line2}`;
    spinnerLabel.textContent = "Uploading ID on-chain";

    // --- write the name hash to the blockchain, signed by the user's own wallet ---
    const nameHash = ethers.keccak256(ethers.toUtf8Bytes(name));
    const contract = await getContractWithSigner();
    const tx = await contract.register(nameHash);
    await tx.wait();

    showResult(`Verified and registered on-chain as ${name}.`, "ok");
    sealEl.classList.add("show");
  } catch (err) {
    console.error(err);
    showResult("Verification or on-chain registration failed. See console for details.", "error");
  } finally {
    spinnerLabel.textContent = "Verifying ID match";
    spinner.classList.remove("show");
    verifyBtn.textContent = "Verify & Register";
    verifyBtn.disabled = false;
  }
});

function showResult(message, kind) {
  resultText.textContent = message;
  resultText.className = `status-text ${kind}`;
}

function showStatus(el, message, kind) {
  el.textContent = message;
  el.className = `status-text ${kind}`;
}

// ---------------- Grant / revoke access (on-chain) ----------------
grantBtn.addEventListener("click", async () => {
  const viewer = grantAddressInput.value.trim();

  if (!connectedAddress) {
    showStatus(accessStatus, "Connect your wallet first.", "error");
    return;
  }
  if (!ethers.isAddress(viewer)) {
    showStatus(accessStatus, "Enter a valid wallet address.", "error");
    return;
  }

  try {
    showStatus(accessStatus, "Confirm in MetaMask...", "ok");
    const contract = await getContractWithSigner();
    const tx = await contract.grant_access(viewer);
    await tx.wait();
    showStatus(accessStatus, `Access granted to ${viewer}.`, "ok");
  } catch (err) {
    console.error(err);
    showStatus(accessStatus, "Failed to grant access. See console for details.", "error");
  }
});

revokeBtn.addEventListener("click", async () => {
  const viewer = grantAddressInput.value.trim();

  if (!connectedAddress) {
    showStatus(accessStatus, "Connect your wallet first.", "error");
    return;
  }
  if (!ethers.isAddress(viewer)) {
    showStatus(accessStatus, "Enter a valid wallet address.", "error");
    return;
  }

  try {
    showStatus(accessStatus, "Confirm in MetaMask...", "ok");
    const contract = await getContractWithSigner();
    const tx = await contract.revoke_access(viewer);
    await tx.wait();
    showStatus(accessStatus, `Access revoked for ${viewer}.`, "ok");
  } catch (err) {
    console.error(err);
    showStatus(accessStatus, "Failed to revoke access. See console for details.", "error");
  }
});

// ---------------- Look up a record (permission-checked by the backend) ----------------
lookupBtn.addEventListener("click", async () => {
  const owner = lookupAddressInput.value.trim();

  if (!connectedAddress) {
    showStatus(lookupStatus, "Connect your wallet first.", "error");
    return;
  }
  if (!ethers.isAddress(owner)) {
    showStatus(lookupStatus, "Enter a valid wallet address.", "error");
    return;
  }

  try {
    const url = `/lookup?owner=${encodeURIComponent(owner)}&viewer=${encodeURIComponent(connectedAddress)}`;
    const response = await fetch(url);
    const data = await response.json();

    if (!data.ok) {
      showStatus(lookupStatus, data.error || "Lookup failed.", "error");
      return;
    }

    showStatus(lookupStatus, `Registered name: ${data.name}`, "ok");
  } catch (err) {
    console.error(err);
    showStatus(lookupStatus, "Something went wrong reaching the server.", "error");
  }
});