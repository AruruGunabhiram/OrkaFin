# Local fixtures

`users.yaml` is a synthetic, version-controlled local test harness. It is not
production authentication, a Workspace directory, or an OrkaATS permission
export. The `.invalid` email domain, display names, user IDs, candidate IDs, and
authorization response IDs are deliberately fictional and must never be replaced
with real personal information or credentials.

The file keeps identity role labels and authorization facts in separate objects.
The local identity resolver reads only the trusted server-side `fixture_id`; it
ignores browser-submitted user IDs, emails, roles, permissions, and actions.
Application services must pass the separate `authorization` object to the
permission evaluator. A role label alone grants nothing.

The fixture policy is provisional and requires the Prompt 7 human review recorded
in `docs/PERMISSION_MODEL.md` before Prompt 8 begins.
## Retrieval evaluation

`retrieval_evaluation.yaml` is the controlled, offline fixture set for Prompt 12.
It contains normalized user questions, a safe page context, trusted permission IDs,
the expected top source ID (or no source), and the expected deterministic intent.
Run it with `python -m orkafin.knowledge.evaluate`; it reports top-source accuracy
only for these fixtures and makes no broader retrieval-quality claim.
