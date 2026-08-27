"""
Convergence test: the property this primitive depends on validators agreeing
about is the banded verdict itself, grounded in the identical criteria and
evidence page. This asserts the STRICT form: two independently-configured
vault instances (each spawned as its own root deployment, not sharing any
state), submitted against the byte-identical criteria and evidence URL,
converge on the IDENTICAL verdict band.

Run with:
    gltest tests/integration/test_convergence.py -v -s --network studionet
"""
from gltest import get_contract_factory, get_default_account, create_accounts
from gltest.assertions import tx_execution_failed

WAIT = dict(wait_interval=8000, wait_retries=60)

CRITERIA = "The page must show a completed, freshly repainted red front door."
URL = "https://example.com/"


def test_identical_evidence_converges_on_the_identical_verdict_band():
    owner = get_default_account()
    client, freelancer = create_accounts(2)

    verdicts = []
    for i in range(2):
        cf = get_contract_factory("CaseVaultFactory")
        contract = cf.deploy(account=owner, args=[client.address, freelancer.address, CRITERIA], **WAIT)
        print(f"\n--- run {i}: deployed at {contract.address} ---")

        r = contract.connect(client).fund(args=[]).transact(value=100, **WAIT)
        assert not tx_execution_failed(r), r
        r = contract.connect(freelancer).submit_evidence(args=[URL]).transact(**WAIT)
        assert not tx_execution_failed(r), r
        r = contract.judge(args=[]).transact(**WAIT)
        assert not tx_execution_failed(r), r

        info = contract.get_case(args=[]).call()
        print("  verdict:", info["last_verdict"])
        verdicts.append(info["last_verdict"])

    print("\nverdicts across both runs:", verdicts)
    assert verdicts[0] == verdicts[1], (
        "identical evidence (byte-identical criteria + evidence URL) must "
        "converge on the identical verdict band across independently-"
        f"deployed vaults; got {verdicts[0]!r} vs {verdicts[1]!r}"
    )
    assert verdicts[0] in ("SATISFIED", "PARTIAL", "UNSATISFIED", "UNKNOWN")
