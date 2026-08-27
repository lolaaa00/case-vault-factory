"""
Adversarial direct-mode test suite for CaseVaultFactory.

Coverage is weighted toward the adversarial list in Phase 4: input
validation on both the factory role (spawn) and the vault role (fund,
submit, judge, dispute, reclaim), access control, the spawn cap, malformed/
empty model output, the explicit UNKNOWN path, idempotency/replay, every
time boundary via warp_to, and every value-moving branch including the
dispute and both reclaim paths.
"""
import sys

sys.path.insert(0, "..")
from conftest import warp_to, as_address  # noqa: E402

CONTRACT = "contracts/case_vault_factory.py"

CRITERIA = "The page must show a completed, freshly repainted red front door."
URL = "https://example.com/"

SATISFIED = '{"verdict": "SATISFIED", "reason": "door is red and freshly painted", "quote": "the door is bright red"}'
PARTIAL = '{"verdict": "PARTIAL", "reason": "door is red but not clearly freshly painted", "quote": "a red door"}'
UNSATISFIED = '{"verdict": "UNSATISFIED", "reason": "door is not red", "quote": "a blue door"}'
UNKNOWN = '{"verdict": "UNKNOWN", "reason": "page is empty", "quote": ""}'


def _deploy(direct_deploy, client, freelancer, criteria=CRITERIA):
    return direct_deploy(CONTRACT, as_address(client).as_hex, as_address(freelancer).as_hex, criteria)


def _fund(c, direct_vm, client, amount=1000):
    direct_vm.startPrank(client)
    direct_vm.value = amount
    c.fund()
    direct_vm.value = 0


def _submitted(c, direct_vm, client, freelancer, amount=1000, url=URL):
    _fund(c, direct_vm, client, amount=amount)
    with direct_vm.prank(freelancer):
        c.submit_evidence(url)


def _judge(c, direct_vm, caller, body):
    direct_vm.mock_web(r".*", {"method": "GET", "status": 200, "body": "irrelevant, judged via mocked LLM"})
    direct_vm.mock_llm(r".*", body)
    try:
        with direct_vm.prank(caller):
            verdict = c.judge()
    finally:
        direct_vm.clear_mocks()
    return verdict


# ---------------------------------------------------------------------------
# __init__ / constructor validation
# ---------------------------------------------------------------------------

def test_deploy_rejects_zero_client_address(direct_deploy, direct_bob):
    raised = False
    try:
        direct_deploy(CONTRACT, "0x" + "00" * 20, as_address(direct_bob).as_hex, CRITERIA)
    except Exception:
        raised = True
    assert raised


def test_deploy_rejects_zero_freelancer_address(direct_deploy, direct_alice):
    raised = False
    try:
        direct_deploy(CONTRACT, as_address(direct_alice).as_hex, "0x" + "00" * 20, CRITERIA)
    except Exception:
        raised = True
    assert raised


def test_deploy_rejects_client_equal_to_freelancer(direct_deploy, direct_alice):
    raised = False
    try:
        direct_deploy(CONTRACT, as_address(direct_alice).as_hex, as_address(direct_alice).as_hex, CRITERIA)
    except Exception:
        raised = True
    assert raised


def test_deploy_rejects_empty_criteria(direct_deploy, direct_alice, direct_bob):
    raised = False
    try:
        direct_deploy(CONTRACT, as_address(direct_alice).as_hex, as_address(direct_bob).as_hex, "   ")
    except Exception:
        raised = True
    assert raised


def test_deploy_configures_the_case_as_awaiting_funding(direct_deploy, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    info = c.get_case()
    assert info["state"] == 0  # STATE_AWAITING_FUNDING
    assert info["client"].lower() == as_address(direct_alice).as_hex.lower()
    assert info["freelancer"].lower() == as_address(direct_bob).as_hex.lower()


# ---------------------------------------------------------------------------
# Factory role: open_case
# ---------------------------------------------------------------------------

def test_open_case_returns_distinct_addresses(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    a1 = c.open_case(as_address(direct_alice).as_hex, as_address(direct_charlie).as_hex, CRITERIA)
    a2 = c.open_case(as_address(direct_alice).as_hex, as_address(direct_charlie).as_hex, CRITERIA)
    assert a1 != a2
    assert int(c.get_children_count()) == 2


def test_open_case_is_permissionless_anyone_may_call_it(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    with direct_vm.prank(direct_charlie):  # a stranger, not the client or freelancer
        addr = c.open_case(as_address(direct_alice).as_hex, as_address(direct_bob).as_hex, CRITERIA)
    assert addr is not None


def test_open_case_enforces_the_max_children_cap(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    for _ in range(64):
        c.open_case(as_address(direct_alice).as_hex, as_address(direct_bob).as_hex, CRITERIA)
    raised = False
    try:
        c.open_case(as_address(direct_alice).as_hex, as_address(direct_bob).as_hex, CRITERIA)
    except Exception:
        raised = True
    assert raised


def test_get_children_pagination_offset_beyond_range_returns_empty(direct_deploy, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    c.open_case(as_address(direct_alice).as_hex, as_address(direct_bob).as_hex, CRITERIA)
    assert list(c.get_children(50, 10)) == []


def test_get_children_returns_the_spawned_addresses_in_order(direct_deploy, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    a1 = c.open_case(as_address(direct_alice).as_hex, as_address(direct_bob).as_hex, CRITERIA)
    a2 = c.open_case(as_address(direct_alice).as_hex, as_address(direct_bob).as_hex, CRITERIA)
    kids = list(c.get_children(0, 10))
    assert [str(x) for x in kids] == [str(a1), str(a2)]


# ---------------------------------------------------------------------------
# Vault role: fund
# ---------------------------------------------------------------------------

def test_fund_rejects_non_client_caller(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    direct_vm.startPrank(direct_bob)
    direct_vm.value = 1000
    raised = False
    try:
        c.fund()
    except Exception:
        raised = True
    direct_vm.value = 0
    assert raised


def test_fund_rejects_zero_value(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    direct_vm.startPrank(direct_alice)
    direct_vm.value = 0
    raised = False
    try:
        c.fund()
    except Exception:
        raised = True
    assert raised


def test_fund_succeeds_and_advances_state(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _fund(c, direct_vm, direct_alice, amount=1000)
    info = c.get_case()
    assert info["state"] == 1  # STATE_FUNDED
    assert info["amount"] == 1000


def test_fund_rejects_once_already_funded(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _fund(c, direct_vm, direct_alice, amount=1000)
    direct_vm.startPrank(direct_alice)
    direct_vm.value = 500
    raised = False
    try:
        c.fund()
    except Exception:
        raised = True
    direct_vm.value = 0
    assert raised


# ---------------------------------------------------------------------------
# Vault role: submit_evidence
# ---------------------------------------------------------------------------

def test_submit_evidence_rejects_non_freelancer_caller(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _fund(c, direct_vm, direct_alice)
    with direct_vm.prank(direct_alice):
        raised = False
        try:
            c.submit_evidence(URL)
        except Exception:
            raised = True
    assert raised


def test_submit_evidence_rejects_before_funding(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    with direct_vm.prank(direct_bob):
        raised = False
        try:
            c.submit_evidence(URL)
        except Exception:
            raised = True
    assert raised


def test_submit_evidence_rejects_non_http_url(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _fund(c, direct_vm, direct_alice)
    with direct_vm.prank(direct_bob):
        raised = False
        try:
            c.submit_evidence("ftp://not-http.test/x")
        except Exception:
            raised = True
    assert raised


def test_submit_evidence_succeeds_and_advances_state(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    info = c.get_case()
    assert info["state"] == 2  # STATE_SUBMITTED
    assert info["evidence_url"] == URL


def test_resubmission_is_allowed_and_clears_the_prior_verdict(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_bob):
        c.submit_evidence(URL)
    info = c.get_case()
    assert info["last_verdict"] == ""
    assert info["state"] == 2  # STATE_SUBMITTED
    assert info["revision_count"] == 2
    assert info["judged_this_revision"] is False


# ---------------------------------------------------------------------------
# Security fix (post-review): each evidence revision judgeable only once,
# resubmission bounded, and a non-extendable hard deadline.
# ---------------------------------------------------------------------------

def test_judge_cannot_be_re_rolled_against_the_same_unchanged_evidence(direct_deploy, direct_vm, direct_alice, direct_bob):
    """The exact vulnerability: after a non-SATISFIED verdict, judge() must
    refuse a second call against the identical evidence -- a permissionless
    caller re-rolling hoping validators eventually hallucinate SATISFIED."""
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    verdict1 = _judge(c, direct_vm, direct_alice, UNSATISFIED)
    assert verdict1 == "UNSATISFIED"
    assert c.get_case()["judged_this_revision"] is True
    raised = False
    try:
        _judge(c, direct_vm, direct_bob, SATISFIED)  # even a caller trying a friendlier mock cannot re-roll
    except Exception:
        raised = True
    assert raised, "judge() must refuse a second call against the same unrevised evidence"


def test_a_fresh_revision_after_a_non_satisfied_verdict_can_be_judged_again(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_bob):
        c.submit_evidence(URL)  # a genuinely new revision
    verdict2 = _judge(c, direct_vm, direct_alice, SATISFIED)
    assert verdict2 == "SATISFIED"


def test_evidence_revisions_are_capped_and_the_freelancer_cannot_resubmit_forever(direct_deploy, direct_vm, direct_alice, direct_bob):
    """The exact vulnerability: the freelancer could resubmit indefinitely
    to keep clearing the verdict and resetting the dispute window. Now
    bounded at MAX_EVIDENCE_REVISIONS."""
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)  # revision 1
    for _ in range(3):
        _judge(c, direct_vm, direct_alice, UNSATISFIED)
        with direct_vm.prank(direct_bob):
            c.submit_evidence(URL)  # revisions 2, 3, 4
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_bob):
        c.submit_evidence(URL)  # revision 5 -- exactly at the cap
    assert c.get_case()["revision_count"] == 5
    raised = False
    try:
        _judge(c, direct_vm, direct_alice, UNSATISFIED)
        with direct_vm.prank(direct_bob):
            c.submit_evidence(URL)  # revision 6 -- must be rejected
    except Exception:
        raised = True
    assert raised, "resubmission past MAX_EVIDENCE_REVISIONS must be rejected"


def test_hard_deadline_lets_client_reclaim_regardless_of_pending_dispute_window(direct_deploy, direct_vm, direct_alice, direct_bob):
    """The exact vulnerability, closed: even if the freelancer keeps
    resubmitting and re-triggering fresh 72h dispute windows forever, the
    client can always reclaim once the immutable hard_deadline (fixed at
    creation) passes -- computed from created_at alone, never recomputed by
    submission or dispute activity."""
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    # simulate the freelancer stalling with repeated resubmissions right up
    # to the revision cap, each one resetting the 72h dispute window
    for _ in range(3):
        with direct_vm.prank(direct_bob):
            c.submit_evidence(URL)
        _judge(c, direct_vm, direct_alice, UNSATISFIED)
    # the case is still SUBMITTED, dispute window freshly reset each time --
    # but the hard deadline is measured from created_at, not from any of
    # these resubmissions
    warp_to(direct_vm, "2031-01-01T00:00:00Z")  # far past HARD_CASE_DEADLINE_DAYS from any 2020s created_at
    c.reclaim_after_deadline()
    info = c.get_case()
    assert info["state"] == 4  # STATE_REJECTED
    assert info["amount"] == 1000


def test_hard_deadline_does_not_fire_before_it_actually_elapses(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    raised = False
    try:
        c.reclaim_after_deadline()  # dispute window (72h) not elapsed either
    except Exception:
        raised = True
    assert raised, "reclaim must still refuse before either the dispute window or the hard deadline has elapsed"


def test_hard_deadline_is_computed_once_at_creation_and_never_shifts(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    hard_deadline_before = c.get_case()["hard_deadline"]
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_bob):
        c.submit_evidence(URL)
    hard_deadline_after = c.get_case()["hard_deadline"]
    assert hard_deadline_before == hard_deadline_after


# ---------------------------------------------------------------------------
# Vault role: judge
# ---------------------------------------------------------------------------

def test_judge_rejects_when_no_evidence_pending(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _fund(c, direct_vm, direct_alice)
    raised = False
    try:
        c.judge()
    except Exception:
        raised = True
    assert raised


def test_judge_satisfied_releases_to_the_freelancer(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    verdict = _judge(c, direct_vm, direct_alice, SATISFIED)
    assert verdict == "SATISFIED"
    info = c.get_case()
    assert info["state"] == 3  # STATE_RELEASED


def test_judge_unsatisfied_opens_a_dispute_window(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    verdict = _judge(c, direct_vm, direct_alice, UNSATISFIED)
    assert verdict == "UNSATISFIED"
    info = c.get_case()
    assert info["state"] == 2  # still SUBMITTED, dispute window open
    assert info["dispute_deadline"] != ""


def test_judge_partial_also_opens_a_dispute_window(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    verdict = _judge(c, direct_vm, direct_alice, PARTIAL)
    assert verdict == "PARTIAL"
    assert c.get_case()["state"] == 2


def test_judge_rejects_once_already_released(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, SATISFIED)
    raised = False
    try:
        c.judge()
    except Exception:
        raised = True
    assert raised


def test_a_failed_fetch_never_pays_out_and_never_marks_the_case_unsatisfied(direct_deploy, direct_vm, direct_alice, direct_bob):
    """Proven by never mocking the web call, which raises inside
    gl.nondet.web.render deterministically in direct mode when no mock
    matches -- the leader's own try/except turns that into UNKNOWN."""
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    direct_vm.mock_llm(r".*", SATISFIED)  # even if the model WOULD say SATISFIED
    with direct_vm.prank(direct_alice):
        verdict = c.judge()
    direct_vm.clear_mocks()
    assert verdict == "UNKNOWN"
    assert c.get_case()["state"] == 2  # still SUBMITTED, nothing paid


def test_malformed_json_from_model_defaults_to_unknown(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    verdict = _judge(c, direct_vm, direct_alice, "not json at all, no braces")
    assert verdict == "UNKNOWN"


def test_model_inventing_an_out_of_band_verdict_is_overruled_to_unknown(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    verdict = _judge(c, direct_vm, direct_alice, '{"verdict": "MOSTLY", "reason": "x", "quote": ""}')
    assert verdict == "UNKNOWN"


def test_judge_is_permissionless(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    verdict = _judge(c, direct_vm, direct_charlie, SATISFIED)  # a stranger triggers it
    assert verdict == "SATISFIED"


# ---------------------------------------------------------------------------
# Dispute path
# ---------------------------------------------------------------------------

def test_dispute_rejects_non_party_caller(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_charlie):
        raised = False
        try:
            c.dispute()
        except Exception:
            raised = True
    assert raised


def test_dispute_rejects_before_a_verdict_exists(direct_deploy, direct_vm, direct_alice, direct_bob):
    """Without a verdict already existing, dispute() must not let a client
    bypass judgement entirely by disputing the instant evidence lands."""
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    with direct_vm.prank(direct_alice):
        raised = False
        try:
            c.dispute()
        except Exception:
            raised = True
    assert raised


def test_dispute_succeeds_and_sets_a_deadline(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_bob):
        c.dispute()
    info = c.get_case()
    assert info["state"] == 5  # STATE_DISPUTED


def test_resolve_dispute_rejects_non_client_caller(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_bob):
        c.dispute()
    with direct_vm.prank(direct_bob):
        raised = False
        try:
            c.resolve_dispute(True)
        except Exception:
            raised = True
    assert raised


def test_resolve_dispute_release_true_pays_the_freelancer(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_bob):
        c.dispute()
    with direct_vm.prank(direct_alice):
        c.resolve_dispute(True)
    assert c.get_case()["state"] == 3  # STATE_RELEASED


def test_resolve_dispute_release_false_refunds_the_client(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_bob):
        c.dispute()
    with direct_vm.prank(direct_alice):
        c.resolve_dispute(False)
    assert c.get_case()["state"] == 4  # STATE_REJECTED


# ---------------------------------------------------------------------------
# Deadline-based reclaim
# ---------------------------------------------------------------------------

def test_reclaim_rejects_before_submission_window_elapses(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _fund(c, direct_vm, direct_alice)
    with direct_vm.prank(direct_alice):
        raised = False
        try:
            c.reclaim_after_deadline()
        except Exception:
            raised = True
    assert raised


def test_reclaim_succeeds_exactly_at_the_submission_window_boundary(direct_deploy, direct_vm, direct_alice, direct_bob):
    warp_to(direct_vm, "2026-01-01T00:00:00.000000Z")
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _fund(c, direct_vm, direct_alice)
    warp_to(direct_vm, "2026-01-31T00:00:00.000000Z")  # exactly 30 days later
    with direct_vm.prank(direct_alice):
        c.reclaim_after_deadline()
    assert c.get_case()["state"] == 6  # STATE_REFUNDED


def test_reclaim_rejects_one_second_before_the_submission_boundary(direct_deploy, direct_vm, direct_alice, direct_bob):
    warp_to(direct_vm, "2026-01-01T00:00:00.000000Z")
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _fund(c, direct_vm, direct_alice)
    warp_to(direct_vm, "2026-01-30T23:59:59.000000Z")
    with direct_vm.prank(direct_alice):
        raised = False
        try:
            c.reclaim_after_deadline()
        except Exception:
            raised = True
    assert raised


def test_reclaim_after_non_satisfied_verdict_is_permissionless_and_refunds_the_client(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    warp_to(direct_vm, "2026-01-01T00:00:00.000000Z")
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    warp_to(direct_vm, "2026-01-04T00:00:01.000000Z")  # 72h + 1s later
    with direct_vm.prank(direct_charlie):  # a stranger, not either party
        c.reclaim_after_deadline()
    assert c.get_case()["state"] == 4  # STATE_REJECTED


def test_reclaim_after_dispute_silence_is_permissionless_and_refunds_the_client(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    warp_to(direct_vm, "2026-01-01T00:00:00.000000Z")
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, UNSATISFIED)
    with direct_vm.prank(direct_bob):
        c.dispute()
    warp_to(direct_vm, "2026-01-04T00:00:01.000000Z")  # 72h + 1s later, client went silent
    with direct_vm.prank(direct_charlie):
        c.reclaim_after_deadline()
    assert c.get_case()["state"] == 4  # STATE_REJECTED


def test_reclaim_rejects_in_a_non_reclaimable_state(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob)
    _judge(c, direct_vm, direct_alice, SATISFIED)
    raised = False
    try:
        c.reclaim_after_deadline()
    except Exception:
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def test_get_case_reflects_full_lifecycle_fields(direct_deploy, direct_vm, direct_alice, direct_bob):
    c = _deploy(direct_deploy, direct_alice, direct_bob)
    _submitted(c, direct_vm, direct_alice, direct_bob, amount=777)
    info = c.get_case()
    assert info["amount"] == 777
    assert info["criteria"] == CRITERIA
