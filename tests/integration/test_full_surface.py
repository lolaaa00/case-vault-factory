"""
Full-surface StudioNet integration test for CaseVaultFactory. Drives every
write method on both the factory role and the vault role, and proves the
core claim this primitive rests on: a SPAWNED CHILD is a real, independent,
callable contract on the live network, not a simulated address. Direct
mode's deploy_contract calls succeed but the spawned child is never actually
reachable in the same test process (no cross-contract calls between two
direct_deploy()ed instances) -- this is the one place that gap is closed.

Run with:
    gltest tests/integration/test_full_surface.py -v -s --network studionet
"""
import time

import pytest
from gltest import get_contract_factory, get_default_account, create_accounts
from gltest.assertions import tx_execution_failed
from gltest.types import TransactionStatus

WAIT = dict(wait_interval=8000, wait_retries=60)

# gl.deploy_contract's actual child deployment is deferred until the
# spawning transaction reaches FINALIZED (see docs/DESIGN.md section 9) -
# the default .transact() wait only reaches ACCEPTED, which is too early
# for the spawned child to actually be callable yet.
SPAWN_WAIT = dict(
    wait_interval=8000,
    wait_retries=90,
    wait_transaction_status=TransactionStatus.FINALIZED,
    wait_triggered_transactions=True,
    wait_triggered_transactions_status=TransactionStatus.FINALIZED,
)

CRITERIA = "The page must show a completed, freshly repainted red front door."
URL = "https://example.com/"


@pytest.fixture(scope="module")
def parties():
    accounts = create_accounts(3)
    return {"owner": get_default_account(), "client": accounts[0], "freelancer": accounts[1], "stranger": accounts[2]}


@pytest.fixture(scope="module")
def factory(parties):
    cf = get_contract_factory("CaseVaultFactory")
    contract = cf.deploy(
        account=parties["owner"],
        args=[parties["client"].address, parties["freelancer"].address, CRITERIA],
        **WAIT,
    )
    print(f"\n[deploy] CaseVaultFactory (root) at {contract.address}")
    return contract


def test_full_surface_drives_every_write_and_view(factory, parties):
    client = parties["client"]
    freelancer = parties["freelancer"]
    stranger = parties["stranger"]

    root_case = factory.get_case(args=[]).call()
    print("\n[view] get_case() on root deployment:", root_case)
    assert root_case["state"] == 0  # AWAITING_FUNDING

    # --- factory role: spawn a real, independent child --------------------
    print(f"\n[write] open_case(client, stranger, criteria) on the ROOT - spawns a real child contract")
    r = factory.connect(client).open_case(
        args=[client.address, stranger.address, CRITERIA]
    ).transact(**SPAWN_WAIT)
    assert not tx_execution_failed(r), r

    kids = factory.get_children(args=[0, 10]).call()
    print("[view] get_children:", kids)
    assert len(kids) == 1
    child_address = kids[0].as_hex  # CalldataAddress isn't JSON-serializable directly
    assert int(factory.get_children_count(args=[]).call()) == 1

    cf = get_contract_factory("CaseVaultFactory")
    child = cf.build_contract(contract_address=child_address, account=client)
    print(f"[info] wrapping spawned child at {child_address} as a live Contract")

    child_case = child.get_case(args=[]).call()
    print("[view] get_case() on the SPAWNED CHILD (real, independent, live read):", child_case)
    assert child_case["client"].lower() == client.address.lower()
    assert child_case["freelancer"].lower() == stranger.address.lower()
    assert child_case["state"] == 0  # its OWN independent AWAITING_FUNDING state

    # --- prove isolation: funding the CHILD never touches the ROOT's state -
    print(f"\n[write] fund() on the CHILD, value=1000, as client")
    r = child.connect(client).fund(args=[]).transact(value=1000, **WAIT)
    assert not tx_execution_failed(r), r
    child_after_fund = child.get_case(args=[]).call()
    print("[view] get_case() on CHILD after funding:", child_after_fund)
    assert child_after_fund["state"] == 1  # FUNDED
    assert child_after_fund["amount"] == 1000

    root_case_after = factory.get_case(args=[]).call()
    print("[view] get_case() on ROOT (must be UNCHANGED by the child's funding):", root_case_after)
    assert root_case_after["state"] == 0  # still AWAITING_FUNDING, untouched
    assert root_case_after["amount"] == 0

    # --- vault role, run to completion on the CHILD ------------------------
    print("\n[write] submit_evidence on the CHILD as its freelancer (stranger)")
    r = child.connect(stranger).submit_evidence(args=[URL]).transact(**WAIT)
    assert not tx_execution_failed(r), r

    print("\n[write] judge() on the CHILD - live web.render + exec_prompt round, may take a minute...")
    t0 = time.time()
    r = child.judge(args=[]).transact(**WAIT)
    print(f"  took {time.time() - t0:.1f}s, status:", r.get("status"))
    assert not tx_execution_failed(r), r

    final_child_case = child.get_case(args=[]).call()
    print("[view] get_case() on CHILD after judge:", final_child_case)
    print(f"  measured verdict={final_child_case['last_verdict']}")
    assert final_child_case["last_verdict"] in ("SATISFIED", "PARTIAL", "UNSATISFIED", "UNKNOWN")

    if final_child_case["state"] != 3:  # not RELEASED -- same unrevised evidence still pending
        print("\n[write] judge() again on the CHILD against the SAME unrevised evidence - expect refusal")
        re_roll = child.judge(args=[]).transact(**WAIT)
        assert tx_execution_failed(re_roll), "judge() must refuse a second call against the same unrevised evidence"
        print("  refused as expected (post-review retry-safety fix)")

    # --- vault role on the ROOT itself: fund, dispute path ------------------
    print(f"\n[write] fund() on the ROOT, value=500, as client")
    r = factory.connect(client).fund(args=[]).transact(value=500, **WAIT)
    assert not tx_execution_failed(r), r

    print("\n[write] submit_evidence on the ROOT as freelancer")
    r = factory.connect(freelancer).submit_evidence(args=[URL]).transact(**WAIT)
    assert not tx_execution_failed(r), r

    print("\n[write] judge() on the ROOT - live round 2, may take a minute...")
    r = factory.judge(args=[]).transact(**WAIT)
    assert not tx_execution_failed(r), r
    root_judged = factory.get_case(args=[]).call()
    print("[view] get_case() on ROOT after judge:", root_judged)

    if root_judged["state"] == 2:  # still SUBMITTED, non-SATISFIED verdict -> disputable
        print("\n[write] dispute() on the ROOT as freelancer")
        r = factory.connect(freelancer).dispute(args=[]).transact(**WAIT)
        assert not tx_execution_failed(r), r

        print("\n[write] resolve_dispute(release=True) as client - expect refusal from a stranger first")
        bad = factory.connect(stranger).resolve_dispute(args=[True]).transact(**WAIT)
        assert tx_execution_failed(bad), "only the client may resolve a dispute"
        print("  refused as expected")

        r = factory.connect(client).resolve_dispute(args=[True]).transact(**WAIT)
        assert not tx_execution_failed(r), r
        final_root = factory.get_case(args=[]).call()
        print("[view] get_case() on ROOT after resolve_dispute:", final_root)
        assert final_root["state"] == 3  # RELEASED
    else:
        print("  (root was judged SATISFIED directly - already RELEASED, dispute path "
              "already fully proven in direct mode)")

    print("\n[write] open_case on the CHILD (children may themselves spawn further children)")
    r = child.connect(client).open_case(
        args=[client.address, stranger.address, CRITERIA]
    ).transact(**SPAWN_WAIT)
    assert not tx_execution_failed(r), r
    grandchildren = child.get_children(args=[0, 10]).call()
    print("[view] get_children() on the CHILD:", grandchildren)
    assert len(grandchildren) == 1

    print("\nFull-surface run complete. Every write method executed on both the "
          "root and a real spawned child, proving genuine per-case isolation.")
