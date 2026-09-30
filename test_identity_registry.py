"""
Automated tests for identity_registry.vy

Runs entirely on a simulated local blockchain (via titanoboa) - no gas,
no MetaMask, no real network involved. Every test starts from a
completely fresh, empty copy of the contract.

Run with:
    py -3.12 -m pytest contract/test_identity_registry.py -v
"""

import boa
import pytest
from eth_utils import keccak


# Three fake admin wallets, generated fresh for testing only.
# These are throwaway test accounts created by titanoboa - NOT your
# real admin wallets. Nothing here touches real funds or real identity.
ADMIN_1 = boa.env.generate_address()
ADMIN_2 = boa.env.generate_address()
ADMIN_3 = boa.env.generate_address()

# Regular (non-admin) test users, for registration tests.
ALICE = boa.env.generate_address()
BOB = boa.env.generate_address()

ONE_YEAR = 365 * 24 * 60 * 60


def name_hash(name: str) -> bytes:
    """Stand-in for what script.js sends: keccak256(name)."""
    return keccak(text=name)


@pytest.fixture
def contract():
    """A fresh, freshly-deployed copy of the contract for each test."""
    return boa.load("contract/identity_registry.vy", ADMIN_1, ADMIN_2, ADMIN_3)


# ---------------------------------------------------------------------
# Registration + expiry cap
# ---------------------------------------------------------------------

def test_register_with_normal_expiry_succeeds(contract):
    with boa.env.prank(ALICE):
        expiry = boa.env.evm.patch.timestamp + ONE_YEAR
        contract.register(name_hash("Alice"), expiry)
    assert contract.registered(ALICE) is True


def test_register_with_expiry_too_far_out_fails(contract):
    with boa.env.prank(ALICE):
        expiry = boa.env.evm.patch.timestamp + (20 * ONE_YEAR)  # past the 15-year cap
        with boa.reverts("Expiry too far in the future"):
            contract.register(name_hash("Alice"), expiry)


def test_register_with_past_expiry_fails(contract):
    with boa.env.prank(ALICE):
        expiry = boa.env.evm.patch.timestamp - 1
        with boa.reverts("Expiry must be in the future"):
            contract.register(name_hash("Alice"), expiry)


# ---------------------------------------------------------------------
# Salting - same name from two different wallets must produce
# two different stored name_hash values
# ---------------------------------------------------------------------

def test_same_name_different_wallets_produce_different_hashes(contract):
    expiry = boa.env.evm.patch.timestamp + ONE_YEAR

    with boa.env.prank(ALICE):
        contract.register(name_hash("Jesse Murphy"), expiry)

    with boa.env.prank(BOB):
        contract.register(name_hash("Jesse Murphy"), expiry)

    hash_alice = contract.name_hash(ALICE)
    hash_bob = contract.name_hash(BOB)
    assert hash_alice != hash_bob


# ---------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------

def test_grant_and_revoke_access(contract):
    expiry = boa.env.evm.patch.timestamp + ONE_YEAR
    with boa.env.prank(ALICE):
        contract.register(name_hash("Alice"), expiry)
        contract.grant_access(BOB)

    assert contract.has_access(ALICE, BOB) is True

    with boa.env.prank(ALICE):
        contract.revoke_access(BOB)

    assert contract.has_access(ALICE, BOB) is False


def test_owner_always_has_access_to_own_record(contract):
    assert contract.has_access(ALICE, ALICE) is True


# ---------------------------------------------------------------------
# Multisig admin control - pause / unpause
# ---------------------------------------------------------------------

def test_non_admin_cannot_propose_pause(contract):
    with boa.env.prank(ALICE):
        with boa.reverts("Not an admin"):
            contract.propose_pause()


def test_single_approval_does_not_trigger_pause(contract):
    with boa.env.prank(ADMIN_1):
        contract.propose_pause()  # proposal #1

    with boa.env.prank(ADMIN_2):
        contract.approve(1)  # 1st approval only

    assert contract.paused() is False


def test_two_approvals_triggers_pause(contract):
    with boa.env.prank(ADMIN_1):
        contract.propose_pause()  # proposal #1

    with boa.env.prank(ADMIN_2):
        contract.approve(1)  # 1st approval

    with boa.env.prank(ADMIN_3):
        contract.approve(1)  # 2nd approval -> should auto-execute

    assert contract.paused() is True


def test_registration_blocked_while_paused(contract):
    with boa.env.prank(ADMIN_1):
        contract.propose_pause()
    with boa.env.prank(ADMIN_2):
        contract.approve(1)
    with boa.env.prank(ADMIN_3):
        contract.approve(1)

    assert contract.paused() is True

    with boa.env.prank(ALICE):
        expiry = boa.env.evm.patch.timestamp + ONE_YEAR
        with boa.reverts("Registrations are currently paused"):
            contract.register(name_hash("Alice"), expiry)


def test_unpause_restores_registration(contract):
    # Pause first
    with boa.env.prank(ADMIN_1):
        contract.propose_pause()
    with boa.env.prank(ADMIN_2):
        contract.approve(1)
    with boa.env.prank(ADMIN_3):
        contract.approve(1)
    assert contract.paused() is True

    # Now unpause
    with boa.env.prank(ADMIN_1):
        contract.propose_unpause()  # proposal #2
    with boa.env.prank(ADMIN_2):
        contract.approve(2)
    with boa.env.prank(ADMIN_3):
        contract.approve(2)
    assert contract.paused() is False

    # Registration should work again
    with boa.env.prank(ALICE):
        expiry = boa.env.evm.patch.timestamp + ONE_YEAR
        contract.register(name_hash("Alice"), expiry)
    assert contract.registered(ALICE) is True


def test_cannot_approve_same_proposal_twice_from_same_admin(contract):
    with boa.env.prank(ADMIN_1):
        contract.propose_pause()
        contract.approve(1)  # ADMIN_1's first approval on their own proposal
        with boa.reverts("Already approved"):
            contract.approve(1)  # trying again should fail


def test_max_validity_can_be_updated_by_admins(contract):
    new_cap = 5 * ONE_YEAR  # tighten from 15 years down to 5

    with boa.env.prank(ADMIN_1):
        contract.propose_max_validity(new_cap)  # proposal #1

    with boa.env.prank(ADMIN_2):
        contract.approve(1)
    with boa.env.prank(ADMIN_3):
        contract.approve(1)

    assert contract.max_validity_seconds() == new_cap

    # An expiry that was fine under the old 15-year cap should now fail
    with boa.env.prank(ALICE):
        expiry = boa.env.evm.patch.timestamp + (10 * ONE_YEAR)
        with boa.reverts("Expiry too far in the future"):
            contract.register(name_hash("Alice"), expiry)