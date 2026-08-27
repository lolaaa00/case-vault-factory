# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
Project Tracker - a worked consumer example for CaseVaultFactory. Contains
NONE of the primitive's own machinery: no exec_prompt, no eq_principle, no
web fetching, and no gl.deploy_contract anywhere in this file.

What it does: after spawning a case directly on a CaseVaultFactory instance
(via its own open_case), anyone permissionlessly registers a pointer here --
(vault_address, project_name) -- against a project label. This tracker never
re-judges anything and never trusts the pointer's implied status; every read
pulls the referenced vault's own `get_case` view live, so a project label
cannot claim to be "released" once the underlying vault's real state says
otherwise. This is the same pull-model integration pattern as this repo's
other worked examples, applied here to a project directory instead of a
single shared registry -- since each case here is already its own contract,
this tracker's only job is giving those independent addresses a human-
readable label and a single place to browse them.

Complete integration surface used here (<=10 lines):

    vault = gl.get_contract_at(vault_address)
    info = vault.view().get_case()
    is_released = info["state"] == 3       # STATE_RELEASED
    is_open = info["state"] in (0, 1, 2)   # AWAITING_FUNDING / FUNDED / SUBMITTED
"""

from genlayer import *


@gl.contract_interface
class ICaseVaultFactory:
    class View:
        def get_case(self) -> dict: ...

    class Write:
        pass


STATE_RELEASED = 3
STATE_OPEN_STATES = (0, 1, 2)

MAX_NAME_CHARS = 80
MAX_PROJECTS_PER_REGISTRANT = 300


@allow_storage
class Project:
    vault_address: Address
    name: str
    registrant: Address


class ProjectTracker(gl.Contract):
    """
    A read-side directory over one or more independently-spawned
    CaseVaultFactory vaults. Registering a project is a purely
    deterministic write: it stores a label and a pointer, and never
    verifies the referenced vault actually exists or belongs to the
    caller, because that would require calling back into the vault during
    a write. This tracker's only consequential decision (what a project's
    status currently shows) is made later, at read time, straight off the
    vault's own live state.
    """

    projects: TreeMap[u256, Project]
    next_project_id: u256
    projects_by_registrant: TreeMap[str, DynArray[u256]]

    def __init__(self) -> None:
        self.next_project_id = u256(0)

    @gl.public.write
    def register_project(self, vault_address: str, name: str) -> u256:
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME_CHARS:
            raise gl.vm.UserError("EXPECTED: name required, 1-80 chars")

        addr = vault_address if isinstance(vault_address, Address) else Address(vault_address)
        if bytes(addr.as_bytes) == b"\x00" * Address.SIZE:
            raise gl.vm.UserError("EXPECTED: vault_address must not be the zero address")

        registrant = gl.message.sender_address
        registrant_addr = registrant if isinstance(registrant, Address) else Address(registrant)
        key = registrant_addr.as_hex
        bucket = self.projects_by_registrant.get_or_insert_default(key)
        if len(bucket) >= MAX_PROJECTS_PER_REGISTRANT:
            raise gl.vm.UserError("EXPECTED: this registrant already has the maximum tracked projects")

        project_id = self.next_project_id
        self.next_project_id = u256(int(project_id) + 1)

        p = self.projects.get_or_insert_default(project_id)
        p.vault_address = addr
        p.name = name.strip()[:MAX_NAME_CHARS]
        p.registrant = registrant_addr

        bucket.append(project_id)

        return project_id

    @gl.public.view
    def get_project(self, project_id: u256) -> dict:
        p = self.projects.get(project_id)
        if p is None:
            raise gl.vm.UserError("EXPECTED: unknown project id")
        return {
            "vault_address": p.vault_address.as_hex,
            "name": p.name,
            "registrant": p.registrant.as_hex,
        }

    @gl.public.view
    def project_status(self, project_id: u256) -> dict:
        """Pulls the referenced vault's CURRENT case state straight from
        the vault contract - this tracker holds no cached status of its
        own, so it can never go stale relative to what the vault actually
        resolved."""
        p = self.projects.get(project_id)
        if p is None:
            raise gl.vm.UserError("EXPECTED: unknown project id")

        vault = gl.get_contract_at(p.vault_address)
        info = vault.view().get_case()
        state = int(info["state"])

        return {
            "name": p.name,
            "is_open": state in STATE_OPEN_STATES,
            "is_released": state == STATE_RELEASED,
            "state": state,
            "last_verdict": info["last_verdict"],
        }

    @gl.public.view
    def projects_for(self, registrant: str) -> list:
        addr = registrant if isinstance(registrant, Address) else Address(registrant)
        bucket = self.projects_by_registrant.get(addr.as_hex)
        if bucket is None:
            return []
        return [int(bucket[i]) for i in range(len(bucket))]

    @gl.public.view
    def get_next_id(self) -> u256:
        return self.next_project_id
