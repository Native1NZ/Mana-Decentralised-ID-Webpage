# @version ^0.4.0
"""
Tuakiri Identity Registry
======================================================

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
"""

registered: public(HashMap[address, bool])
name_hash: public(HashMap[address, bytes32])
expiry: public(HashMap[address, uint256])
access: public(HashMap[address, HashMap[address, bool]])  # owner => viewer => allowed

event Registered:
    owner: address

event AccessGranted:
    owner: address
    viewer: address

event AccessRevoked:
    owner: address
    viewer: address


@external
def register(hashed_name: bytes32, expiry_timestamp: uint256):
    """Register (or update) the caller's identity anchor, with an expiry date."""
    assert expiry_timestamp > block.timestamp, "Expiry must be in the future"
    self.registered[msg.sender] = True
    self.name_hash[msg.sender] = hashed_name
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