# @version ^0.4.0
"""
Tuakiri Identity Registry
==========================================================

Stores a tamper-proof anchor for each registered identity (a hash of
the verified name, not the name itself - the real name is kept off-chain
in the Flask backend, encrypted at rest) and an on-chain access-control
list controlling who is allowed to view each owner's record.

Privacy model:
    - Anyone can see THAT an address is registered, and what addresses
      it has granted access to (this data isn't sensitive).
    - Nobody can see the actual name from the chain alone - it never
      gets stored here. The name hash only lets you VERIFY a name
      against what was registered, not read it.
    - Access control is enforced on-chain: only the owner can grant or
      revoke a viewer's permission, and only with a transaction signed
      by the owner's own wallet.

Admin control:
    - A fixed set of 3 admin wallets, set once at deployment.
    - Any admin can propose pausing/unpausing registrations, or
      changing the max allowed ID validity period.
    - A proposal only takes effect once 2 of the 3 admins approve it.
"""

registered: public(HashMap[address, bool])
name_hash: public(HashMap[address, bytes32])
expiry: public(HashMap[address, uint256])
access: public(HashMap[address, HashMap[address, bool]])  # owner => viewer => allowed

admins: public(address[3])
REQUIRED_APPROVALS: constant(uint256) = 2

paused: public(bool)
max_validity_seconds: public(uint256)

proposal_count: public(uint256)
proposal_action: public(HashMap[uint256, String[32]])
proposal_value: public(HashMap[uint256, uint256])
proposal_approved_by: public(HashMap[uint256, HashMap[address, bool]])
proposal_approval_count: public(HashMap[uint256, uint256])
proposal_executed: public(HashMap[uint256, bool])

event Registered:
    owner: address

event AccessGranted:
    owner: address
    viewer: address

event AccessRevoked:
    owner: address
    viewer: address

event ProposalCreated:
    id: uint256
    action: String[32]
    value: uint256
    proposer: address

event ProposalApproved:
    id: uint256
    approver: address
    approvals: uint256

event ProposalExecuted:
    id: uint256
    action: String[32]


@deploy
def __init__(admin1: address, admin2: address, admin3: address):
    self.admins[0] = admin1
    self.admins[1] = admin2
    self.admins[2] = admin3
    self.max_validity_seconds = 15 * 365 * 24 * 60 * 60
    self.paused = False


@internal
@view
def _is_admin(addr: address) -> bool:
    return addr == self.admins[0] or addr == self.admins[1] or addr == self.admins[2]


@external
def register(hashed_name: bytes32, expiry_timestamp: uint256):
    """Register (or update) the caller's identity anchor, with an expiry date."""
    assert not self.paused, "Registrations are currently paused"
    assert expiry_timestamp > block.timestamp, "Expiry must be in the future"
    assert expiry_timestamp <= block.timestamp + self.max_validity_seconds, "Expiry too far in the future"
    self.registered[msg.sender] = True
    self.name_hash[msg.sender] = keccak256(concat(hashed_name, convert(msg.sender, bytes32)))
    self.expiry[msg.sender] = expiry_timestamp
    log Registered(owner=msg.sender)


@external
def grant_access(viewer: address):
    """Allow `viewer` to look up the caller's registered name off-chain."""
    assert self.registered[msg.sender], "not registered yet"
    self.access[msg.sender][viewer] = True
    log AccessGranted(owner=msg.sender, viewer=viewer)


@external
def revoke_access(viewer: address):
    """Remove a previously granted viewer's permission."""
    self.access[msg.sender][viewer] = False
    log AccessRevoked(owner=msg.sender, viewer=viewer)


@view
@external
def has_access(owner: address, viewer: address) -> bool:
    """True if `viewer` is allowed to see `owner`'s registered name."""
    if owner == viewer:
        return True
    return self.access[owner][viewer]


@view
@external
def is_verified(owner: address) -> bool:
    """True if `owner` registered and their ID hasn't expired."""
    return self.registered[owner] and block.timestamp < self.expiry[owner]


@external
def propose_pause():
    assert self._is_admin(msg.sender), "Not an admin"
    self.proposal_count += 1
    pid: uint256 = self.proposal_count
    self.proposal_action[pid] = "pause"
    log ProposalCreated(id=pid, action="pause", value=0, proposer=msg.sender)


@external
def propose_unpause():
    assert self._is_admin(msg.sender), "Not an admin"
    self.proposal_count += 1
    pid: uint256 = self.proposal_count
    self.proposal_action[pid] = "unpause"
    log ProposalCreated(id=pid, action="unpause", value=0, proposer=msg.sender)


@external
def propose_max_validity(new_value: uint256):
    assert self._is_admin(msg.sender), "Not an admin"
    self.proposal_count += 1
    pid: uint256 = self.proposal_count
    self.proposal_action[pid] = "max_validity"
    self.proposal_value[pid] = new_value
    log ProposalCreated(id=pid, action="max_validity", value=new_value, proposer=msg.sender)


@external
def approve(proposal_id: uint256):
    assert self._is_admin(msg.sender), "Not an admin"
    assert not self.proposal_executed[proposal_id], "Already executed"
    assert not self.proposal_approved_by[proposal_id][msg.sender], "Already approved"
    self.proposal_approved_by[proposal_id][msg.sender] = True
    self.proposal_approval_count[proposal_id] += 1
    log ProposalApproved(id=proposal_id, approver=msg.sender, approvals=self.proposal_approval_count[proposal_id])
    if self.proposal_approval_count[proposal_id] >= REQUIRED_APPROVALS:
        self._execute(proposal_id)


@internal
def _execute(proposal_id: uint256):
    action: String[32] = self.proposal_action[proposal_id]
    if action == "pause":
        self.paused = True
    elif action == "unpause":
        self.paused = False
    elif action == "max_validity":
        self.max_validity_seconds = self.proposal_value[proposal_id]
    self.proposal_executed[proposal_id] = True
    log ProposalExecuted(id=proposal_id, action=action)
