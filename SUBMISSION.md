# Submission

**Title:** Case Vault Factory — Every Case Is Its Own Independently-Deployed Contract

**Description (1000 chars, verified programmatically against
`SUBMISSION_DESCRIPTION.txt` via
`python3 -c "print(len(open(path).read().rstrip(chr(10))))"`):** see
`SUBMISSION_DESCRIPTION.txt` in this folder — the exact text submitted, kept
as its own file so the character count is independently reproducible.

## Evidence links

- **GitHub repo:** https://github.com/lolaaa00/case-vault-factory
- **StudioNet contract address:** `0xE1019C9f9eb2aeFFd09D1673689D19F0de2E9661`
  — canonical deployment, redeployed after the security fix below.
  Full-surface, convergence, and the worked example's own integration test
  were re-run against this exact deployment and two others to prove the
  fixed mechanism live (see README's "Measured on live consensus" for exact
  numbers: a spawned child was funded independently while the parent's own
  case stayed completely untouched, proving genuine per-case storage
  isolation; a real judged round returned `UNSATISFIED` in 47.2s, and a
  second `judge()` call against that same unrevised evidence was correctly
  refused live; the child itself then spawned its own grandchild, proving
  recursive spawning still works post-fix).
- **Explorer:** https://explorer-studio.genlayer.com/address/0xE1019C9f9eb2aeFFd09D1673689D19F0de2E9661
- **Studio import:** open `https://studio.genlayer.com` and import
  `0xE1019C9f9eb2aeFFd09D1673689D19F0de2E9661`

## Security fix (post-review, 2026-08-27)

An external reviewer flagged that after a non-SATISFIED verdict, anyone
could call `judge()` again on the identical unrevised evidence
indefinitely, and the freelancer could resubmit evidence forever, clearing
the verdict and resetting the dispute window each time. Fixed: each
evidence revision is now judgeable at most once, resubmission is capped at
`MAX_EVIDENCE_REVISIONS` (5), and a `hard_deadline` fixed once at case
creation — never recomputed by any submission, judge, or dispute call —
guarantees the client an eventual exit. See `docs/DESIGN.md` section 7 for
the full writeup.

## Git hygiene

Verified with:

```bash
git log --format='%B' -- "intelligent contract/(case-vault-factory)" | grep -i "co-authored\|claude\|generated with"
```

No matches — no AI/agent attribution in any commit message.
