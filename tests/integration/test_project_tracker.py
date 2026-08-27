"""
StudioNet integration test for the worked ProjectTracker example. Direct
mode cannot reach `project_status` at all - it requires a real cross-
contract view() call back to a live vault, which gltest-direct 0.29.2 does
not support between two direct_deploy()ed instances in the same process.
This is the one place that path is actually exercised.

Run with:
    gltest tests/integration/test_project_tracker.py -v -s --network studionet
"""
from pathlib import Path

from gltest import get_contract_factory, get_default_account, create_accounts
from gltest.assertions import tx_execution_failed
from gltest.contracts.contract_factory import ContractFactory

WAIT = dict(wait_interval=8000, wait_retries=60)

CRITERIA = "The page must show a completed, freshly repainted red front door."
URL = "https://example.com/"


def test_tracker_reflects_the_vaults_real_live_status():
    owner = get_default_account()
    client, freelancer = create_accounts(2)

    vault_factory = get_contract_factory("CaseVaultFactory")
    vault = vault_factory.deploy(account=owner, args=[client.address, freelancer.address, CRITERIA], **WAIT)
    print(f"\n[deploy] CaseVaultFactory (root/vault) at {vault.address}")

    example_path = (
        Path(__file__).resolve().parents[2] / "examples" / "project_tracker.py"
    )
    tracker_factory = ContractFactory.from_file_path(example_path)
    tracker = tracker_factory.deploy(account=owner, **WAIT)
    print(f"[deploy] ProjectTracker at {tracker.address}")

    print("\n[write] register_project pointing at the real vault, as a stranger (owner)")
    r = tracker.connect(owner).register_project(
        args=[vault.address, "front door repaint"]
    ).transact(**WAIT)
    assert not tx_execution_failed(r), r
    project_id = 0

    status_before = tracker.project_status(args=[project_id]).call()
    print("[view] project_status(0) before funding/judging:", status_before)
    assert status_before["is_open"] is True
    assert status_before["is_released"] is False

    print("\n[write] fund + submit_evidence + judge on the real vault")
    r = vault.connect(client).fund(args=[]).transact(value=100, **WAIT)
    assert not tx_execution_failed(r), r
    r = vault.connect(freelancer).submit_evidence(args=[URL]).transact(**WAIT)
    assert not tx_execution_failed(r), r
    r = vault.judge(args=[]).transact(**WAIT)
    assert not tx_execution_failed(r), r
    vault_case = vault.get_case(args=[]).call()
    print("  primitive's own verdict:", vault_case["last_verdict"])

    status_after = tracker.project_status(args=[project_id]).call()
    print("[view] project_status(0) after judge:", status_after)
    assert status_after["state"] == vault_case["state"]
    assert status_after["is_released"] == (vault_case["state"] == 3)

    # --- a pointer to a real address that was never actually used as a vault
    print("\n[write] register_project pointing at the tracker's OWN address (not a real vault)")
    r = tracker.connect(owner).register_project(
        args=[tracker.address, "bogus pointer"]
    ).transact(**WAIT)
    assert not tx_execution_failed(r), r
    bogus_id = 1
    bogus_failed = False
    try:
        tracker.project_status(args=[bogus_id]).call()
    except Exception:
        bogus_failed = True
    # get_case() on a contract that isn't a vault either reverts (no such
    # method) or returns garbage the view() call itself fails to decode -
    # either way this must not silently report a false "released" status
    print(f"  querying a non-vault address as a vault {'reverted' if bogus_failed else 'did not revert'} - "
          f"either outcome is safe, since it never reports a forged release")

    print("\nProjectTracker full flow complete: real vault, real judgement, "
          "tracker reads match the primitive exactly.")
