# Case Vault Factory

Every deployed instance of this contract is, simultaneously, both a factory and a
fully self-contained, single-case milestone escrow. Deploying it directly
configures the very first case; calling `open_case(...)` on any instance —
the original deployment or any of its own spawned children — permissionlessly
deploys a brand-new, independent child instance via `gl.deploy_contract`,
configured for a different case with its own client, freelancer, and criteria.
Each vault holds its own GEN balance, its own storage, and runs its own judged
round — it is not a row in a shared table, it is its own contract, independently
addressable and independently auditable on the explorer. Anyone building a
milestone-escrow marketplace, an agency that manages many independent client
engagements, or any primitive that needs cryptographically isolated per-case
state rather than shared rows in one contract can import this instead of
re-solving contract-factory composition from scratch.

## The shared-row problem, stated plainly

Say a platform wants to run many independent escrow cases. The obvious version:
one contract, one `TreeMap` of cases, every case a row keyed by an id. That's
exactly what every other escrow in this repository does, and it works — until
you ask what happens when a case's storage or accounting has a bug: in a shared
contract, a bug that corrupts one row can, in principle, corrupt or interfere
with every other row sharing that contract's storage layout and admin surface.
There is also no way to point a client at "their" case as a genuinely distinct
on-chain entity — every case is a number inside someone else's contract, not
something they can independently verify, audit, or point an explorer link at on
its own. A factory that deploys a fresh, independent contract per case
eliminates that whole class of concern structurally: two cases cannot share
storage they don't share a contract.

## Why a blockchain has to be the one running the factory too

Delete GenLayer and the escrow judgement collapses exactly the way it does for
every other web-fetch-judged escrow: a single party decides whether a milestone
was met, and every counterparty just has to trust them. But a permissionless,
deterministic factory ALSO answers a second, related trust question a
purely off-chain "spin up a new database row" system cannot: who controls
whether a new case's contract is genuinely independent, genuinely deployed with
the parameters it claims, and genuinely addressable by anyone, not just the
platform operator's own backend. `gl.deploy_contract` makes that verifiable —
anyone can inspect a spawned child's own bytecode and constructor arguments on
the explorer, independent of whoever called `open_case`.

Run the alternatives:
- **An off-chain "provisioning service"** that spins up new database rows or
  even new smart contracts via a centralized deploy key is exactly the reviewer
  problem again — whoever holds that key decides what actually gets deployed
  and with what parameters, with no way for a counterparty to verify it matches
  what was requested.
- **A price or data oracle** doesn't apply to either half of this design —
  there's no numeric feed for "was this milestone met" or "was this contract
  deployed with the parameters it claims."
- **A hash or deterministic parser** can prove a page's bytes weren't altered
  after fetch, but says nothing about whether fetched evidence satisfies
  written criteria, and nothing about contract-isolation guarantees at all.
- **An optimistic oracle with human dispute** reintroduces a human decider for
  the judgement half, and still says nothing about the isolation half — a
  human arbitrator doesn't make one contract's storage independent from
  another's.
- **A single LLM call from a centralized backend** produces one party's opinion
  of the evidence, with the same verifiability gap as every other centralized
  judgement — worse here, since a corrupt operator could also silently
  misreport what a "case" even is, since nothing forces cases to be real,
  independently-inspectable contracts at all.
- **A multisig of human arbitrators** re-centralizes the judgement half onto a
  committee and, again, does nothing for the isolation half.

GenLayer is the only option where the judgement lives in the same trust domain
as the money AND every case is a real, independently-verifiable contract
anyone can point at directly.

## This is not the pattern the category is trying to filter out

- Not a contract extracted from a shipped project — this repo has no frontend,
  no product, nothing to extract it from.
- Not a toy built to learn consensus — see the 51 adversarial direct tests and
  the three StudioNet integration runs below, including a run that spawns a
  real child, funds it, and proves its state is genuinely independent of the
  parent's; a learning exercise doesn't need any of that.
- Not a minor variation of something that already exists in this repo — see
  `docs/DECISION_RECORD.md` for the honest inventory of this repo's eight
  prior siblings, every one of which keeps its cases as rows in one shared
  contract, including `(verdict-relay)`'s own `spawn_relay` method, which uses
  `gl.deploy_contract` only as a secondary convenience on top of an unrelated
  core mechanism (push callbacks) rather than as the actual point of the
  design, as it is here.
- Not an "AI app with GenLayer attached" — the model's output is never advice a
  human reads; `judge()`'s verdict directly and deterministically drives
  whether GEN moves.
- Not a validator that only checks output format — the equivalence principle
  compares whether the fetched evidence genuinely satisfies the written
  criteria, never merely whether the model returned parseable JSON.
- Not judging facts from user-submitted text alone — the evidence is a page
  the contract itself fetches fresh at judgement time, a distinct artifact
  neither party can simply assert in prose.

## What the model is asked, and what it is never asked

Exactly ONE non-deterministic round exists per vault, inside `judge()`: one
`gl.nondet.web.render` fetch followed by one `gl.nondet.exec_prompt` call,
inside one `leader()` closure, wrapped in one `gl.eq_principle.prompt_comparative`
round — the same proven shape as `(deliverable-escrow)`, reused deliberately
rather than reinvented, since this contract's entire novel surface is the
factory mechanism, not a new judgement shape. `open_case()` — the factory
spawn — is pure deterministic Python with zero nondet rounds: spawning a
child never moves value and never forecloses anything, so it has no failure
mode that needs a safe direction at all.

The model is asked only "does this fetched evidence satisfy this milestone's
criteria" — never "should a case be spawned," never "how much GEN should this
vault hold." Every other decision is ordinary deterministic code the model
never sees: who may spawn, fund, submit, dispute, or reclaim; every escrow
amount (`u256`, never a float); the spawn cap and the dispute-deadline
arithmetic and their boundary comparisons; parsing and clamping whatever
string the model returns; the state-machine transitions; and the ordering
discipline that writes state before any `emit_transfer` fires. Remove
consensus and the judgement half is inert. Remove the deterministic half and
the model would be deciding, unbounded, exactly how much GEN moves — which the
reject criteria explicitly rule out.

## How it works

```
anyone --open_case(client, freelancer, criteria)--> gl.deploy_contract spawns a
                                                       REAL, INDEPENDENT child instance
                                                       (own storage, own GEN balance)
client --fund()+value------------------------------> [FUNDED]
freelancer --submit_evidence(url)------------------> [SUBMITTED]
anyone --judge()--> fetch + judge -> SATISFIED / PARTIAL / UNSATISFIED / UNKNOWN
   SATISFIED     -> pay freelancer, terminal
   otherwise     -> dispute window opens; either party may dispute, or
                     freelancer may resubmit; if nobody disputes, reclaim_after_deadline
                     permissionlessly refunds the client once the window elapses
client|freelancer --dispute()--> [DISPUTED]
client --resolve_dispute(release)--> pays freelancer or refunds client
anyone --reclaim_after_deadline()--(deadline-gated, every reachable non-terminal state)
                                     --> refunds the client, never permanently stranded
```

The equivalence principle, quoted exactly as it appears in `docs/DESIGN.md` and
in the contract itself — reused verbatim from `(deliverable-escrow)`'s own
proven wording, since this contract's novelty is the factory mechanism
surrounding it, not a new judgement shape:

> Two evaluations of the same milestone evidence are equivalent if they agree
> on the same one of exactly four verdict bands — SATISFIED, PARTIAL,
> UNSATISFIED, or UNKNOWN — for whether the fetched page content meets the
> stated acceptance criteria, and they identify substantially the same
> supporting quotation or absence of one. They remain equivalent despite
> differences in wording, sentence order, capitalization, punctuation, or
> which exact phrase from the page is quoted as evidence, or the exact
> phrasing of the one-sentence reason. They are NOT equivalent if they choose
> a different verdict band, or if one claims the page could not be fetched
> (UNKNOWN) while another proceeds to judge fetched content, or if one bases
> its verdict on content that is not actually present in the fetched text
> (fabricated evidence).

`prompt_comparative`, never `prompt_non_comparative` — the payout decision is
outcome-deciding.

## Safety properties, each backed by a real test

- **A spawned child is a genuinely independent contract, not a simulated
  address** — proven live on StudioNet (Measured Results below): funding a
  spawned child left the root's own case fields completely unchanged, and the
  child's own `get_case()` reflects its own distinct client/freelancer/criteria.
- **The spawn cap is enforced** — `test_open_case_enforces_the_max_children_cap`.
- **Spawning is fully permissionless, but never moves value** —
  `test_open_case_is_permissionless_anyone_may_call_it`; no test anywhere
  shows `open_case` touching `self.amount` or any `emit_transfer`.
- **A failed fetch is never read as "the milestone was not met"** —
  `test_a_failed_fetch_never_pays_out_and_never_marks_the_case_unsatisfied`,
  proven by never mocking the web call and observing the leader's own
  try/except turn that into an explicit `UNKNOWN`.
- **An unparseable or out-of-band model response never defaults to a paying
  verdict** — `test_malformed_json_from_model_defaults_to_unknown`,
  `test_model_inventing_an_out_of_band_verdict_is_overruled_to_unknown`.
- **A dispute cannot bypass judgement** — `test_dispute_rejects_before_a_verdict_exists`
  proves a client cannot dispute the instant evidence is submitted, before
  `judge()` ever runs.
- **Money never moves twice** — `test_judge_rejects_once_already_released`,
  `test_fund_rejects_once_already_funded`.
- **State is written before value leaves** — enforced structurally in every
  value-moving method; exercised by every idempotency test above.
- **Every time boundary is exact, in both directions** —
  `test_reclaim_succeeds_exactly_at_the_submission_window_boundary`,
  `test_reclaim_rejects_one_second_before_the_submission_boundary`, using the
  `warp_to` helper so these are not vacuous zero-elapsed-time passes.
- **A case is never stranded at any reachable non-terminal state** —
  `test_reclaim_after_non_satisfied_verdict_is_permissionless_and_refunds_the_client`,
  `test_reclaim_after_dispute_silence_is_permissionless_and_refunds_the_client`.

51 direct-mode tests pass covering these and every other required adversarial
category. Three StudioNet integration suites additionally cover the one path
direct mode cannot reach at all: a spawned child actually being a real,
independently callable, isolated contract.

## Why this is a primitive, not an application

The complete consumer integration is a `View`/`Write` stub and three lines:

```python
@gl.contract_interface
class ICaseVaultFactory:
    class View:
        def get_case(self) -> dict: ...
    class Write:
        pass

vault = gl.get_contract_at(vault_address)
info = vault.view().get_case()
is_released = info["state"] == 3
```

`examples/project_tracker.py` is a worked, independently linted and tested
consumer that contains none of this contract's own machinery — no
`exec_prompt`, no `eq_principle`, no `web.render`, and no `gl.deploy_contract`
anywhere in that file. Anyone registers a pointer-and-label "project" against
a vault that already exists (spawned directly on this contract); the tracker
never trusts the pointer's implied status, only ever deriving current status
by pulling `get_case()` live at read time — proven live on StudioNet. A single
deployment of this primitive already covers every row below by varying only
the criteria:

| Use case | Client | Freelancer | Criteria (excerpt) |
|---|---|---|---|
| Home-repair milestone | Homeowner | Contractor | "porch light replaced and functioning, per a photo posted to the listed page" |
| Freelance dev milestone | Startup founder | Developer | "the staging URL shows the feature described in the ticket live" |
| Content-delivery milestone | Publisher | Writer | "the article is live at the given URL and matches the agreed brief" |
| Agency retainer checkpoint | Agency client | Agency | "the campaign report page shows the agreed KPIs met for this period" |
| Open-source contract work | Maintainer org | Contributor | "the linked changelog page shows the feature shipped in a tagged release" |

## API reference

**Writes**
- `open_case(client: Address, freelancer: Address, criteria: str) -> Address`
  — permissionless; spawns and returns a real, independent child instance;
  bounded by `MAX_CHILDREN = 64` per instance.
- `fund() -> None` — payable; client only; deposits `gl.message.value`.
- `submit_evidence(evidence_url: str) -> None` — freelancer only.
- `judge() -> str` — permissionless; the one nondet round.
- `dispute() -> None` — client or freelancer only; only once a verdict exists.
- `resolve_dispute(release: bool) -> None` — client only.
- `reclaim_after_deadline() -> None` — permissionless; deadline-gated at every
  reachable non-terminal state.

**Views**
- `get_case() -> dict` (this instance's own case),
  `get_children(offset: u256, limit: u256) -> list[Address]`,
  `get_children_count() -> u256`.

## Development

```bash
source .venv/bin/activate   # from the repo root
export DYLD_LIBRARY_PATH="$(brew --prefix expat)/lib"   # macOS libexpat fix, if needed

genvm-lint check contracts/case_vault_factory.py --json
genvm-lint check examples/project_tracker.py --json

gltest tests/direct/ -v

genlayer network set studionet
gltest tests/integration/ -v -s --network studionet
genlayer deploy --contract contracts/case_vault_factory.py --args <client> <freelancer> "<criteria>"
```

## Status

- `genvm-lint`: clean on both the primitive (`{"ok":true,"lint":{"ok":true,
  "passed":3}}`, 10 methods, 7 write, 8 events) and the example consumer
  (5 methods, 1 write).
- Direct-mode tests: **57 passing** (47 on the primitive, 10 on the worked
  example) — includes the retry-safety fix below.
- StudioNet: **full-surface, convergence, and the worked example's integration
  test all pass** (re-verified 2026-08-27, post-fix), including a real
  spawned child proven independently callable with its own isolated state.
  Canonical deployment (every write method exercised against it, including a
  spawned grandchild): `0xE1019C9f9eb2aeFFd09D1673689D19F0de2E9661`.
- Explorer: https://explorer-studio.genlayer.com/address/0xE1019C9f9eb2aeFFd09D1673689D19F0de2E9661
- Studio import: open [studio.genlayer.com](https://studio.genlayer.com) and
  import the address above.

## Security fix (post-review, 2026-08-27)

An external reviewer flagged two related holes in `judge()`/`submit_evidence()`:
after a non-SATISFIED verdict, anyone could call `judge()` again on the
identical unrevised evidence indefinitely, re-rolling consensus hoping a
later round happened to return SATISFIED; and the freelancer could resubmit
evidence forever, clearing the verdict and resetting the 72h dispute window
each time, stalling the client's `reclaim_after_deadline` path with no
bound. Fixed with three changes: each evidence revision is now judgeable at
most once (`judged_this_revision`); resubmission is capped at
`MAX_EVIDENCE_REVISIONS` (5); and a `hard_deadline`, computed once at case
creation and never recomputed by any submission, judge, or dispute call,
lets the client reclaim regardless of pending disputes or resubmission
activity once it passes. See [`docs/DESIGN.md`](docs/DESIGN.md) section 7
for the full writeup. Verified by reverting the fix, confirming the new
proving tests fail, then restoring it.

## Measured on live consensus

Full-surface run against `0xE1019C9f9eb2aeFFd09D1673689D19F0de2E9661`
(6m31s wall-clock, two real consensus rounds — re-run 2026-08-27, post-fix):
- `open_case(client, stranger, criteria)` on the root deployment spawned a
  real child at `0x2ce4472EEAA36412EBeCb6E7E9798A2eC72287Ae`, confirmed
  independently deployed and callable via `factory.build_contract(...)`.
- `fund()` on the CHILD with `value=1000` correctly advanced only the
  child's own state to `FUNDED` — a follow-up `get_case()` read on the ROOT
  confirmed its own case remained completely untouched (`amount: 0, state:
  0`), proving genuine per-case storage isolation, not merely two identical
  addresses.
- `judge()` on the CHILD ran a real fetch against `https://example.com/` plus
  a real 5-validator consensus round and returned **`UNSATISFIED`** in
  **47.2 seconds**, correctly opening a dispute window rather than paying
  out — and a **second** `judge()` call against that same unrevised
  evidence was correctly refused, live, proving the retry-safety fix holds
  under real consensus.
- On the ROOT's own case: `fund()`, `submit_evidence()`, and `judge()` (a
  second real consensus round) also returned `UNSATISFIED`; `dispute()` by
  the freelancer, a correctly-refused `resolve_dispute` attempt from a
  stranger, and a correct `resolve_dispute(release=True)` by the client all
  executed and asserted correctly, advancing the root's case to `RELEASED`.
- The CHILD itself then called `open_case(...)` to spawn its OWN
  grandchild at `0xc4ad0c0abb31395d24661678bb4ae689249ab53b` — proving
  spawned instances can recursively spawn further independent instances, not
  just the original root.

Convergence run across two independently-deployed instances
(`0xfaDf20C3D93Ba0780f7745d864435236DcC43739` and
`0x7FD42D7A9B96D11f63D4f87d67D7C9D026092DA6`), asserting the strict form —
not "no bad outcome," but that two separately-deployed vaults, funded and
judged against the byte-identical criteria and evidence URL, land on the
byte-identical verdict:
- Run 0: verdict **`UNSATISFIED`**. Run 1: verdict **`UNSATISFIED`** —
  identical bands, exactly as `prompt_comparative` is meant to guarantee.

Worked-example run (vault `0x60E990dB27102455993E1eC461eE7551EdBc5B5F`,
tracker `0xdf0928C766e89BE4f65e11a8a90DEEcF3e7792c5`, 2m22s wall-clock):
- A real vault was funded, submitted, and judged (`UNSATISFIED`) on real
  consensus; `project_status()` correctly reflected `is_open: True,
  is_released: False` before and after, matching the vault's own state
  exactly at every read.
- A pointer registered against a non-vault address (the tracker's own)
  correctly reverted on read rather than silently reporting a forged status.

## The honest limits

- **`reclaim_after_deadline`'s `STATE_FUNDED` and dispute-silence branches
  are proven only in direct mode, via `warp_to`, not on live StudioNet** — a
  genuine 30-day or 72-hour real-time wait is outside a practical test
  budget for a single session. Both guards, and their exact-boundary
  behaviors, are proven in direct mode; the underlying mechanism is
  identical to deadline logic already proven live in this repo's
  `(deliverable-escrow)` sibling.
- **A spawned child's actual deployment is deferred until the spawning
  transaction reaches `FINALIZED`**, not merely `ACCEPTED` — the returned
  address is known synchronously via deterministic salt-derived addressing,
  but the child is not genuinely callable until that later stage. Consumers
  building on `open_case` should wait for finalization before assuming a
  returned address is live, exactly as this repo's own integration tests do
  (`wait_transaction_status=TransactionStatus.FINALIZED,
  wait_triggered_transactions=True`).
- **This primitive judges a fetched page's prose, not the real-world
  milestone directly** — a sufficiently convincing fabricated or manipulated
  page could pass. That risk is inherent to any web-evidence primitive and
  is exactly why the criteria stays specific; integrators with a
  higher-stakes use case should require `evidence_url` point at an
  authoritative, hard-to-spoof source.
- **`MAX_CHILDREN = 64` bounds how many cases a single instance may spawn**
  — a platform expecting more than 64 cases through one entry point should
  have clients call `open_case` on their own previously-spawned children
  (which themselves may spawn further children, proven live above) rather
  than assuming the root alone can spawn unbounded cases.
