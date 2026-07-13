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
