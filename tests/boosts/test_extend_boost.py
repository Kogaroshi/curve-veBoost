import itertools as it
import math

import brownie
import pytest

DAY = 86400
WEEK = DAY * 7


pytestmark = pytest.mark.usefixtures("boost_bob")


@pytest.mark.parametrize("expiry_delta,cancel_delta", it.product([0, 1], repeat=2))
def test_extend_an_existing_boost_modify_(
    alice, token_id, expire_time, veboost, cancel_time, expiry_delta, cancel_delta
):
    token = token_id(alice.address, 0)
    original_boost_value = veboost.token_boost(token)
    veboost.extend_boost(
        token, 7_500, expire_time + expiry_delta, cancel_time + cancel_delta, {"from": alice}
    )

    assert math.isclose(veboost.token_boost(token), original_boost_value * 1.5)
    assert veboost.token_expiry(token) == expire_time + expiry_delta
    assert veboost.token_cancel_time(token) == cancel_time + cancel_delta


def test_delegator_operator_can_extend_a_boost(
    alice, bob, token_id, expire_time, veboost, cancel_time
):
    veboost.setApprovalForAll(bob, True, {"from": alice})

    token = token_id(alice.address, 0)
    original_boost_value = veboost.token_boost(token)
    veboost.extend_boost(token, 7_500, expire_time + 1, cancel_time + 1, {"from": alice})

    assert math.isclose(veboost.token_boost(token), original_boost_value * 1.5)
    assert veboost.token_expiry(token) == expire_time + 1
    assert veboost.token_cancel_time(token) == cancel_time + 1


def test_only_delegator_or_operator(alice, bob, token_id, expire_time, veboost, cancel_time):
    token = token_id(alice.address, 0)
    with brownie.reverts("dev: only delegator or operator"):
        veboost.extend_boost(token, 7_500, expire_time + 1, cancel_time + 1, {"from": bob})


@pytest.mark.parametrize(
    "pct,msg",
    [
        (0, "dev: percentage must be greater than 0 bps"),
        (10_001, "dev: percentage must be less than 10_000 bps"),
    ],
)
def test_invalid_percentage(alice, token_id, expire_time, pct, msg, veboost, cancel_time):
    token = token_id(alice.address, 0)
    with brownie.reverts(msg):
        veboost.extend_boost(token, pct, expire_time + 1, cancel_time + 1, {"from": alice})


def test_new_cancel_time_must_be_less_than_new_expiry(alice, token_id, expire_time, veboost):
    token = token_id(alice.address, 0)
    with brownie.reverts("dev: cancel time is after expiry"):
        veboost.extend_boost(token, 7_000, expire_time, expire_time + 1, {"from": alice})


def test_new_expiry_must_be_greater_than_min_delegation(
    alice, chain, token_id, cancel_time, veboost
):
    token = token_id(alice.address, 0)
    with brownie.reverts("dev: boost duration must be atleast one day"):
        veboost.extend_boost(token, 7_000, chain.time(), 0, {"from": alice})


def test_new_expiry_must_be_less_than_lock_expiry(
    alice, alice_unlock_time, token_id, cancel_time, veboost
):
    token = token_id(alice.address, 0)
    with brownie.reverts("dev: boost expiration is past voting escrow lock expiry"):
        veboost.extend_boost(token, 7_000, alice_unlock_time + 1, cancel_time, {"from": alice})


def test_expiry_must_be_greater_than_tokens_current_expiry(
    alice, token_id, expire_time, cancel_time, veboost
):
    token = token_id(alice.address, 0)
    with brownie.reverts("dev: new expiration must be greater than old token expiry"):
        veboost.extend_boost(token, 7_000, expire_time - 1, cancel_time, {"from": alice})


def test_decreasing_cancel_time_on_active_token_disallowed(
    alice, token_id, chain, expire_time, cancel_time, veboost
):
    token = token_id(alice.address, 0)
    with brownie.reverts("dev: cancel time reduction disallowed"):
        veboost.extend_boost(token, 7_000, expire_time, cancel_time - 1, {"from": alice})

    chain.mine(timestamp=expire_time)
    veboost.extend_boost(token, 7_000, expire_time + DAY, cancel_time - 1, {"from": alice})


def test_outstanding_negative_boosts_prevent_extending_boosts(
    alice, charlie, chain, token_id, expire_time, cancel_time, veboost
):
    # give charlie our remaining boost
    veboost.create_boost(alice, charlie, 10_000, 0, chain.time() + DAY, 1, {"from": alice})
    # fast forward to a day the boost given to charlie has expired
    chain.mine(timestamp=expire_time - DAY)

    with brownie.reverts("dev: outstanding negative boosts"):
        veboost.extend_boost(
            token_id(alice.address, 0), 7_000, expire_time, cancel_time, {"from": alice}
        )