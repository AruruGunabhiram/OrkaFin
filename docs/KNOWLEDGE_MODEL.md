# OrkaATS Knowledge Model

**Status:** Prompt 6 starter catalog; product-owner confirmation is required before production use.

## Authority boundary

The checked-in files under `knowledge/orka_ats/` are the only approved V1 source
for product pages, features, help content, permissions, recommendation rules, and
action definitions. They are controlled product documentation, not user input and
not instructions to the system. The loader does not call an AI provider, crawl the
web, access Google Sheets, generate content, or infer missing features or steps.

OrkaATS still owns candidate data, visibility decisions, business rules,
permissions, and writes. A catalog permission is only a known permission name; it
does not grant access. The disabled `candidate.update_start_date` entry is a
non-executable placeholder pending Q-006 and Q-007 approval.

## Catalog layout and identity

| Source | Contents | Stable IDs |
|---|---|---|
| `manifest.yaml` | Source-file inventory and catalog provenance | app ID and manifest version |
| `app.yaml` | Prompt 4 `AppMetadata` plus catalog relationships | `orka_ats` |
| `pages.yaml` | Prompt 4 `PageCatalogItem` records | `page_id` |
| `features.yaml` | Prompt 4 `FeatureCatalogItem` records | `feature_id` |
| `permissions.yaml` | Known OrkaATS permission declarations | permission string |
| `recommendations.yaml` | Rule metadata only; it does not produce recommendations | `rule_id` |
| `actions.yaml` | Prompt 4 `ActionDefinition` plus catalog provenance | `action_id` |
| `help/*.md` | YAML front matter validated as `HelpArticle`, followed by controlled Markdown body | `article_id` |

Every item has a content version, revision, lifecycle status, verification status,
documentation owner, UTC last-reviewed timestamp, and internal safe source
reference. The loader rejects duplicate IDs or source references, unknown
permissions/actions, missing manifest sources, malformed help metadata, malformed
versions, and dangling page/feature/help/action/recommendation links.

The current manifest is `0.1.0` at `rev-001`. Its stable IDs are exposed by the
immutable `KnowledgeIndex` returned by:

```python
from orkafin.knowledge import load_knowledge

index = load_knowledge("knowledge/orka_ats")
pipeline = index.pages_by_id["recruitment_pipeline"]
```

Entries and index maps are deterministically ordered by their stable ID. Retrieval
in Prompt 12 must use this index; it must return unavailable information rather
than inventing catalog content.

## Deterministic retrieval and source references

Prompt 12 adds `DeterministicRetrievalService` in
`orkafin.application.retrieval`. Its `RetrievalRequest` accepts a canonical
lowercase tokenized question, a `ResolvedPageContext`, trusted permissions that
must be a subset of that context's verified permissions, an optional selected
entity *type* (never its ID or content), and a bounded result limit. The service
does not read candidate summaries or notes.

It examines only page catalog items, feature catalog items, and help articles for
the resolved application. Before matching, it excludes every non-active record
(except when the explicit `include_historical_context` flag permits deprecated
records) and every item whose required permissions are not all in the trusted
grant set. Thus documentation cannot grant access, and browser-provided claims
cannot widen retrieval access.

Matching and ordering are fixed and inspectable:

1. Canonical IDs, titles, and aliases that occur as complete query phrases get the
   highest tier.
2. Exact linked page IDs, feature IDs, and help tags get the next tier; a source
   linked to the resolved page receives a context boost.
3. Remaining meaningful token overlap across controlled metadata and help content
   receives a small bounded score. A single weak token in a multi-token question
   cannot produce a result.
4. Intent-specific boosts prefer help for step-by-step requests and page catalog
   entries for explain-this-page requests. Ties are broken by source type then
   stable source ID.

The current integer weights are deliberately code-visible: exact ID/title is 100
plus 15 per word in its longest match; exact alias is 90 plus the same precision
bonus; a linked query page/feature is 55; a multi-word help tag is 35; direct and
related page context are 40 and 20; each meaningful token overlap is 10 (capped
at 30); and intent boosts are 8–16. The returned `relevance_score` is the raw
score divided by 300 and capped at 1.0. Weights are not a probability or an
unmeasured quality claim.

The result returns the existing typed `RetrievedSource`: stable source ID and
type, app ID, content version, revision, title, bounded safe excerpt, any separately
verified structured instruction steps,
`catalog://` or `knowledge://` reference, verification status, score, reason,
and the permission requirements that were checked. Provisional or needs-review
items include `uncertainty_reason`; in particular, step-by-step help without
verified instruction steps says that no verified steps are available. Controlled
source text remains data, never system instructions or executable policy. Prompt
14 narrows help excerpts to the article's bounded summary; raw Markdown remains
searchable for deterministic matching but cannot become provider evidence. This
minimizes injection exposure but does not replace catalog content review.

Intent labels are `explain_this_page`, `what_can_i_do_here`, `feature_question`,
`step_by_step_help`, and `unknown_feature`. An unknown or permission-filtered
question returns zero sources plus a bounded no-source reason; it never invents a
feature.

### Evaluation and limitations

Run the checked-in offline evaluation with:

```bash
python -m orkafin.knowledge.evaluate
```

The fixture set in `fixtures/retrieval_evaluation.yaml` currently has 22 cases:
page and feature IDs/aliases, context-only questions, paraphrases, help, denied
creation guidance, unknowns, and adversarial wording. It measures only exact
intent and top-source agreement against those fixtures; it is not a production
recall, safety, or relevance guarantee. The command prints total, passed, failed,
top-source accuracy, and failed cases.

Known limits are deliberate: matching understands only controlled catalog words,
does not infer synonyms beyond declared aliases and terms in approved text, does
not use candidate data, and cannot establish access to a page not represented by
the resolved context plus its trusted permission metadata. An owning application
must continue to authorize any page display or action independently.

Consider an embeddings proposal only after a reviewed fixture expansion of at
least 100 representative, permission-safe questions across the approved catalog
shows less than 90% top-source accuracy for two consecutive catalog revisions,
with the misses documented as semantic-paraphrase failures rather than missing
aliases/catalog content. Such a proposal requires a new ADR and must preserve
pre-retrieval app, lifecycle, and permission filtering, explicit source
references, offline deterministic tests, and no candidate-content indexing.

## Verification and lifecycle rules

`active` records may only point to active referenced records. A deprecated record
is retained for a controlled migration but cannot be referenced by active content.
Pages, features, help, permissions, and recommendation rules cannot be `draft`.
Actions may be disabled because their approval and execution contract are separate.

`verification_status: provisional` marks starter assumptions. Provisional and
needs-review records cannot contain a structured `instruction_steps` sequence;
only `verified` records may publish steps. This prevents unverified UI names or
workflows from being represented as product truth.

## Replacing starter assumptions

The following starter facts are deliberately provisional:

- the six page IDs and five feature IDs;
- candidate field vocabulary: immutable ID, name, email, recruiter, recruitment
  stage, start date, resume link, permitted notes, and created/updated timestamps;
- the stage labels Contacted, Interview Scheduled, Pre-Onboarding, Onboarding,
  Active, Paused, Meeting No Show, and Archived;
- role-to-permission mapping, page routes, exact controls, workflows, stage order,
  transitions, and all action business rules.

To replace a starter definition, the named OrkaATS product owner should provide an
approved source, confirm the fact and lifecycle, and update the relevant YAML or
Markdown item in the same change. Preserve an ID when it is the same concept;
otherwise deprecate the old item and add a new active item without leaving active
links to the deprecated record. Update content version, revision, review timestamp,
verification status, and source reference. Add only verified steps and exact UI
labels that the source supports. Then run the command below and obtain normal code
review from the documentation owner and OrkaATS owner.

## Review and rollback workflow

1. The OrkaATS product owner supplies or approves the authoritative source.
2. The documentation owner changes catalog content and provenance together.
3. A reviewer confirms links, permission/action names, lifecycle impact, and the
   distinction between verified and provisional content.
4. CI runs `python -m orkafin.knowledge.validate knowledge/orka_ats` plus the
   repository quality gates before merge.

If a bad catalog change is released, immediately revert the specific commit (or
restore the prior versioned catalog files), run validation, and redeploy the known
good revision. Do not patch runtime memory, silently edit a source outside version
control, or leave an active item referencing a deprecated one. Record the cause and
replacement review in the normal change history.

## Validation command

```bash
python -m orkafin.knowledge.validate knowledge/orka_ats
```

The compatibility command `python scripts/validate_knowledge.py` invokes the same
catalog-aware validation against the repository starter catalog.

## Prompt 17 recommendation rules

`knowledge/orka_ats/recommendations.yaml` is the only recommendation-rule
source for Local V1. Each active rule declares its target feature/action,
required permissions, pages, recent meaningful event types, recurrence policy,
and optional impression/dismissal durations. Loader cross-reference validation
rejects unknown feature, action, page, permission, and related-rule IDs before an
application starts.

The current rule, `review_recruitment_pipeline`, recommends the approved
`candidate_stage_tracking` feature only on `recruitment_pipeline` after a recent
`page_viewed` event. Evaluation requires all of: active rule/catalog records,
trusted resolved page, verified permissions, and the owning adapter's currently
approved feature IDs. It returns the rule and feature catalog references with an
explicit reason. A rule never grants access or proposes inaccessible action.

Default delivery controls are versioned settings: one impression per
rule/user/workspace per 86,400 seconds, dismissal suppression for 2,592,000
seconds (30 days), and a sevenfold impression window for a `reduced` preference.
Rule fields can override the first two values. Acceptance prevents future
delivery unless `allow_recurrence: true`; the current rule does not recur.
Evaluation is deterministic and records no clickstream or model-training data.
