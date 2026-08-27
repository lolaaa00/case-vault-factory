"""
Direct-mode tests for the worked consumer example
(examples/project_tracker.py).

Deliberately scoped to exclude `project_status`: it calls
`gl.get_contract_at(...)` against a real vault contract, and gltest-direct
0.29.2 does not support live cross-contract calls between two
direct_deploy()ed instances in the same process -- the same known gap
documented in the sibling examples' test suites. Whether that view actually
reflects the vault's live status is verified on StudioNet instead; see
tests/integration/.

What CAN be verified here, deterministically, with only this one contract
deployed: registration bookkeeping, input validation, the zero-address
guard, and the per-registrant cap.
"""
import sys

sys.path.insert(0, "..")
from conftest import as_address  # noqa: E402

TRACKER = "examples/project_tracker.py"
ZERO_ADDR_HEX = "0x" + "00" * 20


def test_register_project_rejects_empty_name(direct_deploy, direct_bob):
    t = direct_deploy(TRACKER)
    addr = as_address(direct_bob).as_hex
    raised = False
    try:
        t.register_project(addr, "")
    except Exception:
        raised = True
    assert raised


def test_register_project_rejects_name_over_max_length(direct_deploy, direct_bob):
    t = direct_deploy(TRACKER)
    addr = as_address(direct_bob).as_hex
    raised = False
    try:
        t.register_project(addr, "x" * 81)
    except Exception:
        raised = True
    assert raised


def test_register_project_rejects_zero_address_vault(direct_deploy):
    t = direct_deploy(TRACKER)
    raised = False
    try:
        t.register_project(ZERO_ADDR_HEX, "porch light repaint")
    except Exception:
        raised = True
    assert raised


def test_register_project_returns_sequential_ids_and_records_fields(direct_deploy, direct_vm, direct_alice, direct_bob):
    t = direct_deploy(TRACKER)
    addr = as_address(direct_bob).as_hex
    with direct_vm.prank(direct_alice):
        p0 = t.register_project(addr, "front door repaint")
        p1 = t.register_project(addr, "porch light repaint")
    assert int(p0) == 0
    assert int(p1) == 1
    info = t.get_project(p0)
    assert info["name"] == "front door repaint"
    assert info["vault_address"].lower() == addr.lower()
    assert info["registrant"].lower() == as_address(direct_alice).as_hex.lower()


def test_register_project_accepts_vault_address_as_hex_string(direct_deploy, direct_bob):
    t = direct_deploy(TRACKER)
    addr_hex = as_address(direct_bob).as_hex
    assert isinstance(addr_hex, str)
    pid = t.register_project(addr_hex, "hex test")
    info = t.get_project(pid)
    assert info["vault_address"].lower() == addr_hex.lower()


def test_projects_for_groups_multiple_projects_by_registrant(direct_deploy, direct_vm, direct_alice, direct_bob):
    t = direct_deploy(TRACKER)
    addr = as_address(direct_bob).as_hex
    with direct_vm.prank(direct_alice):
        p0 = t.register_project(addr, "a")
        p1 = t.register_project(addr, "b")
    with direct_vm.prank(direct_bob):
        t.register_project(addr, "c")
    ids = [int(x) for x in t.projects_for(as_address(direct_alice).as_hex)]
    assert sorted(ids) == sorted([int(p0), int(p1)])
    assert [int(x) for x in t.projects_for(as_address(direct_bob).as_hex)] == [2]


def test_projects_for_unknown_registrant_returns_empty_list(direct_deploy, direct_bob):
    t = direct_deploy(TRACKER)
    assert list(t.projects_for(as_address(direct_bob).as_hex)) == []


def test_get_project_unknown_id_raises(direct_deploy):
    t = direct_deploy(TRACKER)
    raised = False
    try:
        t.get_project(999)
    except Exception:
        raised = True
    assert raised


def test_next_id_increments_monotonically(direct_deploy, direct_bob):
    t = direct_deploy(TRACKER)
    addr = as_address(direct_bob).as_hex
    assert int(t.get_next_id()) == 0
    t.register_project(addr, "a")
    assert int(t.get_next_id()) == 1
    t.register_project(addr, "b")
    assert int(t.get_next_id()) == 2


def test_per_registrant_project_cap_is_enforced(direct_deploy, direct_vm, direct_alice, direct_bob):
    t = direct_deploy(TRACKER)
    addr = as_address(direct_bob).as_hex
    with direct_vm.prank(direct_alice):
        for i in range(300):
            t.register_project(addr, f"project {i}")
        raised = False
        try:
            t.register_project(addr, "project 300")
        except Exception:
            raised = True
    assert raised, "the 301st project for the same registrant must be rejected"
