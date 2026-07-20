# Local Demo Walkthrough

This walkthrough demonstrates the working Local V1 behavior with synthetic data. Start it with:

```bash
source .venv/bin/activate
python scripts/run_local_demo.py --subject admin
```

Then open <http://127.0.0.1:8000/demo>. The browser sends only app/page/selection hints. The server process chooses the synthetic identity; no browser control can select a role, email, permission, workspace, or action.

## Guided acceptance flow

1. On **Candidate profile** and `CAND-1042`, open **Ask OrkaFin**.
2. Send **Explain this page**. Expect a grounded guidance response and an approved page source.
3. Send **What can I do with candidate profile review?**. Expect catalog-backed feature guidance, not a claim that all controls are available.
4. Send a help question such as **How do I review a candidate?**. If the approved source is provisional or lacks verified steps, expect the safe unavailable/uncertainty behavior rather than invented instructions.
5. Send **Summarize this candidate**. The immediate response may contain permitted standard fields and a `candidate_summary` source. It must not show the fixture email, resume reference, start date, timestamps, or note.
6. Send **What is quantum candidate matching?**. Expect `unavailable_information` with `source_missing` and no source list.
7. Change the selected candidate to `CAND-1099`, then request a summary. Expect a non-disclosing candidate-access denial. `CAND-1099` is private; the response must not say that it exists or disclose its fields.
8. Change the page to **Recruitment pipeline** and choose **No candidate selected**. The widget evaluates the deterministic rule and shows **Review the recruitment pipeline** with two catalog references.
9. Use **Helpful** and **Not helpful** on separate fresh recommendations to record non-suppressing feedback. Use **Accept** to mark a recommendation accepted; it will not repeat for the configured rule. Use **Dismiss** to suppress it for the local configured interval. **Disable recommendations** also stores a disabled preference.
10. Click **Reset conversation**. It clears the browser's conversation ID and response state; it does not erase local audits/events.

## Safe failures

To see the offline state, stop the local FastAPI process, send one question, and observe **Assistant offline**. Restart the launcher before continuing. The widget does not fabricate a cached result.

To see fail-closed identity behavior, stop the launcher and start FastAPI without a fixture subject:

```bash
uvicorn orkafin.main:app --reload
```

The health endpoint still succeeds, but a context, assistant, recommendation, event, or feedback request returns the safe `identity_unverified` envelope. Stop that server and restart the checked launcher afterwards.

## Optional mock action

With the `admin` server subject, **Candidate profile**, and `CAND-1042` selected:

1. Enter a valid date other than the current synthetic `2026-08-17`, such as `2026-10-06`.
2. Click **Preview start-date update**. Review owning app, target, old/new date, affected user/workspace, warning, and reversibility.
3. Click **Confirm update**. The message must state that no action has executed yet.
4. Click **Execute approved update**. A success message is shown only after the mock adapter confirms a matching receipt.
5. Re-select the candidate or resolve the page context; the permitted synthetic start-date value now reflects the mock state.

This action affects only `var/mock_orka_ats_state.json`. It does not invoke Apps Script or change a Google Sheet. To repeat the walkthrough, reset it:

```bash
python -m orkafin.adapters.orka_ats.seed --reset
```

## Observe the local record

After the flow, inspect the OrkaFin-owned event/audit records:

```bash
python scripts/inspect_local_activity.py --kind all --limit 20
```

Expect bounded event types and audit decisions such as `candidate_read`, `permission_denied`, `action_proposed`, and action execution state. The CLI redacts recognizable credentials/emails and does not expose a network endpoint. The user-facing API has no audit read route.

## API-only smoke requests

All examples use synthetic IDs and a server started with `ORKAFIN_LOCAL_FIXTURE_SUBJECT=admin`:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS -X POST http://127.0.0.1:8000/api/v1/assistant/queries \
  -H 'Content-Type: application/json' \
  -d '{"question":"Explain this page.","context":{"app_id":"orka_ats","page":"candidate_profile"}}'
```

The second response contains a generated request ID, grounded content, and approved sources. See [API.md](API.md) for full request/response envelopes. Run the full release gate after any code change; this manual walkthrough supplements but does not replace automated security, integration, E2E, and widget tests.
