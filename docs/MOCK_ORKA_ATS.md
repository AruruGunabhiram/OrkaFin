# Mock OrkaATS adapter

The local adapter registration key is `orka_ats`; its implementation is
`MockOrkaATSAdapter` (`mock_orka_ats`, contract `1.0.0`). It is a deterministic,
synthetic OrkaATS owner for local development and tests, not a stand-in for
Apps Script or production authentication.

Candidate fixtures live in `fixtures/orka_ats/` and are read only by
`src/orkafin/adapters/orka_ats/mock.py`. The adapter exposes only general
contract responses: field-filtered candidate summaries and searches. It does not
provide a raw candidate object or an OrkaFin repository for candidate data.

## Fixture access model

All fixture people, email addresses, candidates, and notes are synthetic.

| Fixture subject | Candidate visibility |
|---|---|
| `recruiter` | `CAND-1042`, with standard fields plus approved contact/start-date/resume fields |
| `limited_viewer` | `CAND-1042`, with only name, recruiter, and stage |
| `admin` | `CAND-1042` and `CAND-1043`, with a broader bounded field set |
| `unverified` or an unknown subject | No identity claims, candidate data, permissions, or context |

`CAND-1099` is private, `CAND-1999` is archived, and unknown candidate IDs are
not available. The summary path returns the same safe not-found outcome for a
private or missing record. `CAND-1042` includes deliberately malicious note text;
notes are neither candidate fields nor search text and are never sent in normal
summaries or events.

Supported pages are `candidate_dashboard`, `candidate_list`,
`candidate_profile`, `recruitment_pipeline`, `candidate_creation_form`, and
`recruiter_filters`. Features are calculated from the verified user and current
page. The adapter advertises `candidate.update_start_date` only to the eligible
admin fixture and implements `execute_approved_action` for that action alone. It
rechecks permission, action availability, candidate visibility, definition
version, parameter hash, current value, and idempotency before mutating state.

## Reset and failure simulation

Reset the optional adapter-owned state file with:

```bash
python -m orkafin.adapters.orka_ats.seed --reset
```

This restores fixture start dates and clears all receipts in
`var/mock_orka_ats_state.json`; it does not touch `var/orkafin.db` or any OrkaFin
persistence repository. Tests can inject a temporary `state_path` so mutable
candidate values and idempotency receipts remain isolated per test.

State schema version 1 contains only start-date overrides and execution receipts
indexed by idempotency key. Reads overlay those values on immutable synthetic
fixtures. Writes use an atomic compare-and-set file replacement. The state store
returns the original receipt for an exact idempotent replay and rejects a key
bound to different request facts.

Tests can construct `MockOrkaATSAdapter` with `MockFailureSimulation`. Its
`failures` mapping accepts an `AdapterCapability` (or capability string) and an
`AdapterErrorCode`, such as `TIMEOUT`, `UNAVAILABLE`, or `VALIDATION_FAILED`.
`latency_seconds` adds a deterministic async delay before the configured result.
`malformed_execution_receipt=True` performs the mock write but returns a
mismatched adapter ID so OrkaFin's no-fabricated-success behavior can be tested.
Failures become the contract's exact typed adapter exceptions.

## Limitations

The mock performs no live Apps Script request, production identity proof, Google
Sheet access, real candidate write, notes permission workflow, or automatic retry.
Its idempotency receipts support local manual reconciliation only. A real OrkaATS
adapter must independently enforce the rules at its system of record and define an
authenticated reconciliation contract. Local mock success proves no live
integration property.
