# Decision Record — Case Vault Factory

## Phase 0 grounding, redone fresh for this contract

```
curl -s https://sdk.genlayer.com/main/_static/ai/api.txt         -> byte-identical to research/sdk-api.txt
curl -s https://docs.genlayer.com/full-documentation.txt         -> byte-identical to research/docs-full.txt
```

Both diffed at zero lines against the locally cached copies. Re-read the
"Factory Pattern" section of `docs-full.txt` specifically for this contract: it
documents reading a child contract's source via `open("/contract/<file>.py")`
inside `__init__`, and confirms `gl.deploy_contract(code=..., args=[...],
salt_nonce=..., on=...)` returns a deterministic, salt-derived address
synchronously even though actual deployment is deferred to the specified stage
(`on='accepted'`/`on='finalized'`). `(verdict-relay)`'s already-shipped
`spawn_relay` method in this repo is a real, StudioNet-proven implementation of
exactly this pattern (self-replicating factory, own-source read with a
direct-mode fallback via `__file__`) — reused here as the load-bearing
mechanism this contract's whole design rests on, not a fresh unverified
technique.

## What this repo's eight prior contracts already cover

1. `(deliverable-escrow)` — 1:1 escrow, web-fetch judgement, single instance.
2. `(payout-batch-dedup)` — embeddings dedup gate.
3. `(photo-proof-bounty)` — user-submitted image judgement, 1:1.
4. `(verdict-relay)` — push-callback composition; `spawn_relay` uses
   `gl.deploy_contract` but only as a **secondary** feature (an owner who wants
   a differently-configured sibling instance) — the contract's actual core
   mechanism is the push callback, not the factory.
5. `(bounty-match-router)` — embeddings ranked matching.
6. `(spec-compliance-bounty)` — `gl.vm.spawn_sandbox` execution-trace evidence.
7. `(parametric-coverage-pool)` — pooled (not 1:1) escrow, solvency accounting.
8. `(appealable-wager)` — two-round staked appeal ladder with slashing.

Every one of the eight, including `verdict-relay`, keeps every case's state in
one shared contract instance (a `TreeMap` slot per case, or a single wager/pool
per deployment). None of them uses contract-per-case isolation as the actual
point of the design. That is the real unclaimed ground: `gl.deploy_contract` as
the **primary**, load-bearing mechanism, not an incidental convenience feature
bolted onto a contract whose core value is something else.

## Twelve candidates

1. **Case vault factory** — a root contract permissionlessly spawns an
   independent, fully self-contained escrow "vault" per case via
   `gl.deploy_contract`; each vault is its own contract with its own GEN
   balance, own storage, own judged round, addressable and auditable on the
   explorer as a distinct entity. *(factory, value)*
2. **Insurance-vault factory** — same mechanism applied to per-policy
   insurance vaults instead of milestone escrow. Close cousin of #1; folded
   in rather than counted separately, see the self-audit below.
3. **Reputation-shard factory** — one child contract per reviewer, tracking
   their own judged review history in isolation. *(factory)* — the
   judgement core ("was this review genuine engagement") drifts toward
   judging facts from user-submitted text alone without a hard evidence
   anchor; discarded on Gate C grounds, same reasoning as a near-identical
   candidate discarded in `(appealable-wager)`'s decision record.
4. **EVM-state-gated access pass** — discarded again this cycle on the same
   confirmed platform limitation as the prior two contracts' decision
   records: EVM contract interaction beyond a plain value transfer does not
   work on Studio.
5. **Seeded-randomness fair draw** — once the seed is fixed the outcome is
   not a judgement; fails Gate A and Gate C, as in every prior contract's
   decision record that considered it.
6. **Upgrade-rights governance charter** — thin judgement core (a proposal's
   own text is not usually contested by two parties the way a payout claim
   is); kept for capability breadth only.
7. **Screenshot-judged visual vault factory** — combines the factory
   mechanism with visual evidence. Discarded per this repo's now-repeated
   audit: web/visual evidence is already represented in five of eight prior
   contracts in some form; the unclaimed ground is the factory mechanism
   itself, which does not need a new evidence type riding along with it to
   be genuinely novel.
8. **Multi-file worker-pool factory** — the documented `Factory Pattern`
   example spawns `num_workers` identical, unconfigured worker contracts at
   `__init__` time. Interesting as a pattern, but "workers" with no
   individual judged escrow logic is infrastructure, not a primitive with a
   real trust story; discarded as too thin to answer "why does this need a
   blockchain" on its own.
9. **Slashed-bond fact-check market** — a single-round staked claim market;
   this was already screened and discarded in `(appealable-wager)`'s
   decision record for being a weaker version of that contract's appeal
   ladder. Not re-litigated here.
10. **Bonded claim race** — multiple claimants race to be first to submit
    evidence for one bounty, each paying a non-refundable listing fee.
    *(value)* — a genuinely different competitive-claim mechanism from
    every prior sibling's serial-reattempt or paired-party shape. Strong
    candidate, not chosen for *this* contract only because it does not
    touch the factory capability this build is specifically targeting;
    recorded here as a promising direction for a future contract instead
    of discarded on merit.
11. **Prediction bond pool** — N-way pooled staking on one binary real-world
    outcome, winners split losers' stakes pro-rata. *(value)* — same
    reasoning as #10: a strong, genuinely distinct value mechanism, set
    aside for this contract only because it does not exercise the factory
    capability, not because it is weak.
12. **Per-case upgradeable vault with governed upgrade rights** — combines
    the factory mechanism with #6's upgrade governance, letting each spawned
    vault have its own `upgraders` set. Interesting compounding idea, but
    doubles the storage/trust-model surface for a benefit ("this specific
    vault's code can be swapped later") that most milestone-escrow use
    cases do not actually need; discarded as scope creep on top of an
    already-sufficient factory story.

**Capabilities actually represented, counted honestly:** contract factories
(1, 2, 3, 7, 8, 12), EVM interop (4), randomness (5), upgradeability (6, 12),
image/screenshot (7), value/staking (1, 2, 9, 10, 11). Six distinct
capabilities explored.

## Self-audit (per the anti-drift addendum)

1. **Count distinct capabilities actually represented — not claimed.** Six,
   as listed above. Candidates 1 and 2 are honestly one mechanism (factory +
   1:1 vault) wearing two subject lines, not two capabilities.
2. **Name the two candidates most similar to each other.** #1 and #2 — a
   milestone vault factory and an insurance vault factory are the identical
   `gl.deploy_contract`-per-case mechanism with a different vault payload.
   #2 is not built as a separate primitive.
3. **What would I have picked if `gl.deploy_contract` did not exist at
   all?** #11, the prediction bond pool — the strongest candidate on this
   list that needs no factory mechanism at all, only pooled value
   accounting and one judged round. It was not chosen for this contract
   specifically because this build is deliberately targeting the one
   capability (factories) that seven prior contracts in this repo have
   never used as a primary mechanism — it is recorded as the next contract
   to build instead of discarded on merit.
4. **Name the strongest discarded candidate and why.** #10, the bonded
   claim race. It is arguably as strong as the chosen idea — a genuinely
   new competitive-settlement mechanism no prior contract has — but was
   held back for the same reason as #11: it does not exercise
   `gl.deploy_contract`, which is this specific contract's target capability.
   Both #10 and #11 are recorded here as real, screened candidates for
   this build's next two contracts, not merely placeholder ideas.

## Gate screening for the chosen idea (#1)

- **Gate A — counterfactual.** Delete GenLayer: a single off-chain service
  decides both whether the milestone is met AND whether a case's records are
  trustworthy against tampering from other cases (since a shared database
  has no cryptographic isolation between rows the way separate contracts do).
  With GenLayer, each case is judged by consensus AND lives in its own
  independently-verifiable contract.
- **Gate B — trust problem.** Funder and claimant, exactly as in
  `(deliverable-escrow)` — neither controls the fetched evidence, and now
  neither has to trust that the platform's shared storage correctly isolates
  their case from every other case ever created through the same factory.
- **Gate C — is it a judgement?** Identical judgement core to
  `(deliverable-escrow)`, already proven live: "does this fetched evidence
  satisfy this milestone's written criteria" is irreducibly semantic.
- **Gate D — would someone else import it?** `open_case(...)` returns a real
  contract address; a consumer's entire integration is calling that method
  and then reading the returned vault's own `get_case()` view — shown in
  README §9.
- **Gate E — consequential decision?** Directly gates real GEN escrow release
  per case, exactly as the underlying vault logic already does.
- **Gate F — originality.** Not on the collision list. Distinct from every
  prior sibling, including `verdict-relay`: this contract's entire reason to
  exist is the factory-per-case isolation; `verdict-relay`'s factory method
  is a secondary convenience on top of an unrelated core mechanism (push
  callbacks).

Chosen: **Case Vault Factory** — see `DESIGN.md` for the full design record.
