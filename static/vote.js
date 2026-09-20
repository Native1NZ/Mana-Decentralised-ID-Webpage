// Tuakiri Mock Election - frontend logic
// Demonstrates gating a real action (voting) behind on-chain identity
// verification. The backend checks contract.registered(address) before
// accepting a vote, and enforces one vote per verified identity.

let connectedAddress = null;
let selectedOption = null;

const connectBtn = document.getElementById("voter-connect-btn");
const walletDisplay = document.getElementById("voter-wallet-display");
const eligibilityStatus = document.getElementById("eligibility-status");
const ballotOptions = document.getElementById("ballot-options");
const voteStatus = document.getElementById("vote-status");
const resultsBars = document.getElementById("results-bars");
const totalVotesEl = document.getElementById("total-votes");

function showStatus(el, message, kind) {
  el.textContent = message;
  el.className = `status-text ${kind}`;
}

function setOptionsEnabled(enabled) {
  document.querySelectorAll(".ballot-option").forEach((btn) => {
    btn.disabled = !enabled;
  });
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
    await checkEligibility();
  } catch (err) {
    console.error(err);
    walletDisplay.value = "Connection rejected";
  }
});

// ---------------- Eligibility check ----------------
async function checkEligibility() {
  if (!connectedAddress) return;

  try {
    const response = await fetch(`/api/vote-status?address=${encodeURIComponent(connectedAddress)}`);
    const data = await response.json();

    if (!data.ok) {
      showStatus(eligibilityStatus, data.error || "Couldn't check eligibility.", "error");
      setOptionsEnabled(false);
      return;
    }

    if (!data.registered) {
      showStatus(
        eligibilityStatus,
        "This wallet hasn't completed identity verification. Register first, then come back.",
        "error"
      );
      setOptionsEnabled(false);
      return;
    }

    if (data.already_voted) {
      showStatus(eligibilityStatus, "This identity has already voted. Thanks for participating!", "ok");
      setOptionsEnabled(false);
      return;
    }

    showStatus(eligibilityStatus, "Identity verified. You're eligible to vote.", "ok");
    setOptionsEnabled(true);
    renderResults(data.options, data.tally);
  } catch (err) {
    console.error(err);
    showStatus(eligibilityStatus, "Something went wrong reaching the server.", "error");
  }
}

// ---------------- Casting a vote ----------------
ballotOptions.addEventListener("click", async (e) => {
  const btn = e.target.closest(".ballot-option");
  if (!btn || btn.disabled) return;

  if (!connectedAddress) {
    showStatus(voteStatus, "Connect your wallet first.", "error");
    return;
  }

  const option = btn.dataset.option;
  setOptionsEnabled(false);
  showStatus(voteStatus, "Confirm the signature request in MetaMask...", "ok");

  try {
    const message = `MANA DID Vote\nAddress: ${connectedAddress}\nOption: ${option}`;
    const provider = new ethers.BrowserProvider(window.ethereum);
    const signer = await provider.getSigner();
    const signature = await signer.signMessage(message);

    showStatus(voteStatus, "Casting your vote...", "ok");

    const response = await fetch("/api/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address: connectedAddress, option, message, signature }),
    });
    const data = await response.json();

    if (!data.ok) {
      showStatus(voteStatus, data.error || "Vote failed.", "error");
      if (data.tally) renderResults(Object.keys(data.tally), data.tally);
      return;
    }

    btn.classList.add("selected");
    showStatus(voteStatus, `Vote recorded for ${option}.`, "ok");
    showStatus(eligibilityStatus, "This identity has already voted. Thanks for participating!", "ok");
    renderResults(Object.keys(data.tally), data.tally);
  } catch (err) {
    console.error(err);
    showStatus(voteStatus, "Something went wrong reaching the server.", "error");
    setOptionsEnabled(true);
  }
});

// ---------------- Results rendering ----------------
function renderResults(options, tally) {
  const total = Object.values(tally).reduce((sum, n) => sum + n, 0);

  resultsBars.innerHTML = "";
  options.forEach((option) => {
    const count = tally[option] || 0;
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;

    const row = document.createElement("div");
    row.className = "result-row";
    row.innerHTML = `
      <div class="result-label"><span>${option}</span><span>${count} vote${count === 1 ? "" : "s"}</span></div>
      <div class="result-track"><div class="result-fill" style="width: ${pct}%"></div></div>
    `;
    resultsBars.appendChild(row);
  });

  totalVotesEl.textContent = `${total} total vote${total === 1 ? "" : "s"} cast`;
}

async function loadResults() {
  try {
    const response = await fetch("/api/vote-results");
    const data = await response.json();
    if (data.ok) renderResults(data.options, data.tally);
  } catch (err) {
    console.error(err);
  }
}

// results are visible to everyone on page load, even before connecting
loadResults();
setOptionsEnabled(false);
