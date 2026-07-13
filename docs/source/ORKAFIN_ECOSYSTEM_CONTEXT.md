# OrkaFin — Google Workspace Ecosystem and Architecture Plan

## Purpose of This Document

This document is the system-level source of truth for OrkaFin.

It explains:

- The current PROJXON / Orka ecosystem.
- The technical constraints created by the Google Workspace environment.
- How Orka applications and OrkaFin should communicate.
- What should remain in Google Apps Script.
- What may later move to Google Cloud.
- How identity, permissions, events, APIs, AI, actions, and audit logs should work.
- The architecture rules that future product, engineering, design, and AI planning must follow.

Any future architecture, feature, workflow, or implementation proposal for OrkaFin should be evaluated against this document.

---

# 1. Company Ecosystem

PROJXON operates primarily inside the Google Workspace ecosystem.

The working environment includes services such as:

- Google Workspace accounts and organizational identities.
- Google Apps Script.
- Google Sheets.
- Google Drive.
- Google Docs.
- Google Forms.
- Gmail.
- Google Calendar.
- Google Meet.
- Google Sites.
- Google Cloud services when a more scalable backend is required.

The current Orka applications are primarily being built as Google Apps Script web applications.

Examples may include:

- Orka ATS.
- Orka SOP.
- Orka Task.
- Orka Flow.
- Orka HR.
- Orka Asset.
- Other Orka OS applications.

These applications may use Google Sheets, Drive, Docs, Forms, Calendar, Gmail, or other Workspace services as their operational data sources.

The system must remain compatible with this ecosystem.

OrkaFin must not be designed as an unrelated standalone product that ignores the Google Workspace foundation.

---

# 2. What OrkaFin Is

OrkaFin is the AI intelligence and agent layer inside Orka OS.

It is not a generic chatbot.

It is not a replacement for the Orka applications.

It is not intended to replicate ChatGPT, Gemini, or unrelated external AI products.

Its purpose is to:

- Understand the Orka application the user is currently using.
- Understand the current page, selected record, or workflow.
- Answer questions about Orka applications and features.
- Provide step-by-step guidance.
- Recommend unused features.
- Recommend the next useful Orka application.
- Learn meaningful user behavior patterns.
- Suggest workflow improvements and automations.
- Preserve useful organizational and project knowledge.
- Perform approved actions through Orka application APIs.
- Respect all application, project, workspace, and user permissions.
- Record important agent actions for accountability.

OrkaFin should eventually act as the shared intelligence layer connecting the Orka OS ecosystem.

---

# 3. Core Architecture Decision

The Orka ecosystem should use a hybrid architecture.

## Google Apps Script remains responsible for:

- Orka application user interfaces.
- Application-specific business logic.
- Google Workspace integrations.
- Reading and writing application-owned data.
- Enforcing application-level permissions.
- Exposing controlled functions or APIs to OrkaFin.
- Sending page context and meaningful events to OrkaFin.
- Executing approved actions requested by OrkaFin.

## OrkaFin is responsible for:

- Understanding user questions.
- Combining current-page context with approved application data.
- Retrieving feature and help knowledge.
- Generating grounded responses.
- Creating recommendations.
- Detecting repeated behavior patterns.
- Suggesting automations.
- Preparing action previews.
- Requesting user confirmation.
- Coordinating approved actions across Orka applications.
- Maintaining user preferences and feedback.
- Recording agent activity and action results.

## Future central backend

The first OrkaFin prototype may run largely in Google Apps Script.

However, the complete production intelligence layer should not be permanently trapped inside Apps Script.

When the system grows, the central OrkaFin service should move to a scalable Google Cloud backend such as:

- Cloud Run for the OrkaFin API and agent orchestration.
- Gemini for AI reasoning and response generation.
- Firestore or Cloud SQL for structured application metadata, user events, preferences, and audit logs.
- Cloud Logging for observability.
- Secret Manager for API keys and service credentials.
- Pub/Sub or Cloud Tasks for asynchronous jobs when required.

This remains compatible with the Google Workspace ecosystem.

The architecture is therefore:

Google Workspace applications in Apps Script  
plus  
a central OrkaFin intelligence service when scale and complexity require it.

---

# 4. High-Level System Architecture

```text
Google Workspace User
        |
        v
Orka Apps built in Google Apps Script
        |
        |-- Current page context
        |-- Selected record context
        |-- User role and permissions
        |-- Meaningful user events
        |-- Controlled read functions
        |-- Approved action functions
        |
        v
OrkaFin Assistant Interface
        |
        v
OrkaFin Intelligence Layer
        |
        |-- Knowledge retrieval
        |-- Feature catalog
        |-- Help content and SOPs
        |-- Recommendation engine
        |-- User behavior signals
        |-- Permission-aware reasoning
        |-- Action planning
        |-- Confirmation flow
        |-- Audit logging
        |
        v
Controlled Orka App APIs / Adapters
        |
        v
Application data updated through the owning Orka app
```

OrkaFin must coordinate the applications.

It must not bypass the applications and directly manipulate all underlying Sheets or Drive files.

---

# 5. The Most Important Architecture Rule

Each Orka application owns its own data and business rules.

For example:

- Orka ATS owns candidate data and recruiting workflows.
- Orka SOP owns SOP records and process rules.
- Orka Task owns task data and task actions.
- Orka HR owns employee and user-related records.
- Orka Flow owns meeting and collaboration workflows.

OrkaFin must request data or actions through the owning application.

## Incorrect design

```text
OrkaFin directly reads and writes every Google Sheet.
```

## Correct design

```text
OrkaFin requests information from Orka ATS.
Orka ATS checks identity and permissions.
Orka ATS returns only allowed information.
OrkaFin prepares a recommendation or action.
The user confirms the action.
OrkaFin requests the action through Orka ATS.
Orka ATS validates and performs the update.
```

This rule is required for security, maintainability, and future scalability.

---

# 6. Standard Orka Application Adapter

Every Orka application should implement a standard adapter that allows OrkaFin to interact with it consistently.

The internal implementation may differ by application, but the external contract should follow the same structure.

Recommended adapter capabilities:

```text
getAppMetadata()
getCurrentContext()
getCurrentUser()
getUserPermissions()
getPageMetadata()
getSelectedEntitySummary()
getAvailableFeatures()
getAvailableActions()
getRecentUserEvents()
searchAllowedRecords()
executeApprovedAction()
logFeedback()
```

Example context response:

```json
{
  "app": "orka_ats",
  "page": "candidate_profile",
  "user": {
    "email": "maya@projxon.com",
    "role": "recruiter"
  },
  "workspace": {
    "id": "workspace_001",
    "name": "PROJXON Recruiting"
  },
  "selectedEntity": {
    "type": "candidate",
    "id": "CAND-1042"
  },
  "permissions": [
    "candidate.view",
    "candidate.edit",
    "task.create"
  ],
  "availableActions": [
    "update_candidate",
    "change_stage",
    "create_task",
    "request_feedback"
  ]
}
```

A standard adapter prevents OrkaFin from becoming a collection of one-off integrations.

---

# 7. How Apps Script Applications Can Expose Data

An Apps Script application can expose controlled functionality in several ways.

## Inside the same Apps Script application

The application UI can call server-side Apps Script functions using:

```text
google.script.run
```

This is useful when the OrkaFin panel is embedded directly inside the same Apps Script web application.

## Through an Apps Script web app endpoint

An Apps Script project can expose HTTP endpoints through:

```text
doGet(e)
doPost(e)
```

These endpoints can receive requests and return JSON.

Example request:

```json
{
  "action": "get_candidate_context",
  "candidateId": "CAND-1042"
}
```

Example response:

```json
{
  "candidateId": "CAND-1042",
  "stage": "Interview Scheduled",
  "recruiter": "maya@projxon.com",
  "availableActions": [
    "change_stage",
    "create_task",
    "request_feedback"
  ]
}
```

## Through a future Cloud Run API

When the system becomes larger, OrkaFin may call a central Cloud Run service, which then communicates with the appropriate Orka application adapter.

The implementation can evolve without changing the product behavior.

---

# 8. Current-Page Context

OrkaFin should not require the user to explain their entire situation every time.

Each Orka application should send current context when the OrkaFin panel opens or when the user changes pages.

Recommended context fields:

```json
{
  "app": "orka_ats",
  "page": "candidate_profile",
  "workspaceId": "workspace_001",
  "userId": "maya@projxon.com",
  "userRole": "recruiter",
  "selectedEntityType": "candidate",
  "selectedEntityId": "CAND-1042",
  "availableActions": [
    "candidate.view",
    "candidate.edit",
    "task.create"
  ]
}
```

This allows OrkaFin to answer questions such as:

- What does this page do?
- What should I do next?
- Can I move this candidate to another stage?
- Who is assigned to this task?
- Which Orka app should I use for this workflow?

---

# 9. User Identity

The Google Workspace identity is the primary authentication layer.

The system should use the authenticated Workspace user wherever possible.

However, identity must be handled carefully because Apps Script identity behavior depends on deployment configuration.

The system must follow these rules:

- Never trust an email address sent only from browser JavaScript.
- Resolve or verify the authenticated user on the server side.
- Map the Workspace user to an Orka user record.
- Use Orka role and permission records for authorization.
- Do not assume that being part of the Workspace means access to all Orka data.
- Test each deployment mode to confirm whether the active user email is available.
- Do not expose application data when identity cannot be verified.

Authentication answers:

```text
Who is the user?
```

Authorization answers:

```text
What is this user allowed to view or do?
```

Both are required.

---

# 10. Permission Model

OrkaFin must never provide broader access than the current user already has.

Permission checks must exist at several levels:

- Workspace-level access.
- Application-level access.
- Role-level access.
- Project-level access.
- Record-level access.
- Field-level access when required.
- Action-level access.
- User-controlled OrkaFin data access preferences.

Examples:

- A recruiter may view candidates but not salary information.
- A project member may view a project but not private admin notes.
- A user may allow OrkaFin to access Orka Task but disable Orka Chat or Orka Vault access.
- A manager may create tasks but may not change organization-wide permissions.
- Only an admin may change another user's access level.

OrkaFin must never bypass these rules.

Every read and write request must be checked by the owning Orka application or a trusted centralized authorization service.

---

# 11. What Orka Applications Should Log

OrkaFin should not track every click or keystroke.

The system should record meaningful business events.

Recommended examples:

- App opened.
- Page viewed.
- Candidate created.
- Candidate updated.
- Candidate stage changed.
- Candidate archived.
- Task created.
- Task assigned.
- Task completed.
- Project created.
- Project member added.
- SOP created.
- SOP approved.
- Meeting created.
- Feedback requested.
- Workflow completed.
- Action failed.
- Recommendation accepted.
- Recommendation dismissed.
- Recommendation edited.
- Automation approved.
- Automation disabled.

Do not log:

- Every character typed.
- Unnecessary message content.
- Passwords.
- Tokens.
- Secrets.
- Sensitive data unrelated to the recommendation.
- Full private content when a safe event summary is sufficient.

Example event:

```json
{
  "eventId": "evt_12345",
  "app": "orka_ats",
  "eventType": "candidate_stage_changed",
  "userId": "maya@projxon.com",
  "workspaceId": "workspace_001",
  "entityType": "candidate",
  "entityId": "CAND-1042",
  "metadata": {
    "previousStage": "Contacted",
    "newStage": "Interview Scheduled"
  },
  "timestamp": "2026-07-13T23:20:00Z"
}
```

---

# 12. Event Flow

Example: a recruiter changes a candidate's stage.

```text
1. The user opens a candidate in Orka ATS.
2. Orka ATS identifies the user.
3. Orka ATS verifies that the user can edit the candidate.
4. The user changes the stage.
5. Orka ATS validates and saves the change.
6. Orka ATS records a candidate_stage_changed event.
7. OrkaFin receives or later reads the event.
8. OrkaFin detects that interview preparation is usually the next step.
9. OrkaFin suggests creating an interview task.
10. The user reviews the proposed action.
11. The user confirms.
12. OrkaFin requests the task through the correct Orka app.
13. The owning application validates and executes the action.
14. OrkaFin records the result in the audit log.
15. User feedback improves future recommendations.
```

---

# 13. OrkaFin Knowledge Sources

OrkaFin should answer only from approved and controlled sources.

Recommended sources include:

- Orka app feature catalogs.
- App page metadata.
- Help documents.
- SOPs.
- Product rules.
- Internal documentation.
- Allowed workspace or project data.
- User permissions.
- User preferences.
- User event history.
- Approved organization knowledge.
- Available application actions.

Each knowledge item should include metadata such as:

```json
{
  "app": "orka_ats",
  "featureId": "candidate_pipeline",
  "featureName": "Candidate Pipeline",
  "description": "Tracks candidates across recruiting stages.",
  "requiredRole": [
    "recruiter",
    "hiring_manager",
    "admin"
  ],
  "helpSource": "approved_document_reference",
  "lastUpdated": "2026-07-01",
  "status": "active"
}
```

This is necessary to reduce hallucinated features and outdated instructions.

---

# 14. Feature Catalog Requirement

Every Orka application must maintain a structured feature catalog.

Minimum fields:

- App ID.
- App name.
- Feature ID.
- Feature name.
- Description.
- User purpose.
- Supported roles.
- Required permissions.
- Page or route.
- Step-by-step instructions.
- Related features.
- Related Orka apps.
- Available actions.
- API or server function.
- Confirmation requirement.
- Status.
- Version.
- Documentation owner.
- Last updated date.

Without this catalog, OrkaFin cannot reliably explain or recommend features.

---

# 15. Action Catalog Requirement

OrkaFin must use an explicit action catalog.

It must not invent executable actions.

Each action should define:

- Action name.
- Owning Orka application.
- User command example.
- Required role.
- Required permission.
- Required input data.
- Validation rules.
- Whether user confirmation is required.
- Whether admin approval is required.
- API or Apps Script function.
- Success response.
- Failure response.
- Audit log fields.
- Whether the action is reversible.
- Whether the action is sensitive or destructive.

Example:

```json
{
  "action": "create_interview_task",
  "ownerApp": "orka_task",
  "requiredPermission": "task.create",
  "confirmationRequired": true,
  "adminApprovalRequired": false,
  "inputs": [
    "candidateId",
    "title",
    "assigneeId",
    "dueDate"
  ],
  "reversible": true,
  "auditRequired": true
}
```

---

# 16. Confirmation Rules

Informational responses do not require confirmation.

Sensitive or state-changing actions require confirmation.

Examples requiring confirmation:

- Creating a task.
- Assigning a user.
- Updating a candidate.
- Changing a candidate stage.
- Sending a message.
- Requesting feedback.
- Booking a meeting.
- Changing access.
- Deleting or archiving information.
- Creating an automation.
- Triggering a cross-app workflow.

Confirmation preview should show:

- What action will happen.
- Which application will perform it.
- Which record will be changed.
- Who will be affected.
- Important values.
- Whether the action can be undone.

Example:

```text
Create interview preparation task

Candidate: John Smith
Assignee: Daniel
Due date: July 18, 2026
Application: Orka Task

[Confirm] [Edit] [Cancel]
```

---

# 17. Audit Logging

Every important OrkaFin action must be traceable.

Audit records should include:

- Requesting user.
- Workspace.
- Application.
- Requested action.
- Data accessed.
- Permission result.
- Confirmation result.
- Final parameters.
- Target record.
- Application endpoint or function used.
- Success or failure.
- Error message.
- Timestamp.
- Correlation or request ID.

Example:

```json
{
  "requestId": "req_9821",
  "requestedBy": "maya@projxon.com",
  "workspaceId": "workspace_001",
  "action": "create_interview_task",
  "targetApp": "orka_task",
  "permissionCheck": "passed",
  "confirmation": true,
  "status": "success",
  "timestamp": "2026-07-13T23:30:00Z"
}
```

---

# 18. OrkaFin User Interface

The expected interface is a reusable assistant panel available across Orka applications.

Recommended behavior:

- Small OrkaFin icon in the bottom-right corner.
- Opens into a compact assistant panel.
- Understands the current app and page.
- Shows suggested prompts.
- Supports typed input in the first version.
- May support microphone input later.
- Displays recommendation cards.
- Displays confirmation previews.
- Provides privacy and application-access settings.
- Allows users to disable or reduce recommendations.
- Allows users to give feedback.
- Shows sources or app references when useful.

Suggested first prompts:

- Explain this page.
- What can I do here?
- Show me the next step.
- Recommend an unused feature.
- Which Orka app should I use?
- Summarize this record.
- Help me create a task.

---

# 19. OrkaFin Response Types

OrkaFin outputs may include:

## Explanation

```text
This page shows candidates grouped by recruitment stage.
```

## Step-by-step guidance

```text
1. Select the candidate.
2. Open the Stage menu.
3. Choose Interview Scheduled.
4. Save the change.
```

## Feature recommendation

```text
You are manually tracking candidate stages. The Orka ATS pipeline view may reduce repeated updates.
```

## Application recommendation

```text
You are creating many follow-up tasks. Orka Task may be the next useful Orka application.
```

## Productivity nudge

```text
Four interview follow-ups are overdue.
```

## Action preview

```text
I can create four interview-preparation tasks and assign them to Daniel. Confirm?
```

## Action result

```text
Four tasks were created successfully.
```

## Safe refusal

```text
You do not have permission to view this project.
```

## Uncertainty response

```text
I could not find an approved Orka feature that performs this action.
```

---

# 20. End-to-End Example

## Scenario

A recruiter is editing a candidate in Orka ATS.

## Inputs

```json
{
  "user": "maya@projxon.com",
  "role": "recruiter",
  "app": "orka_ats",
  "page": "candidate_profile",
  "candidateId": "CAND-1042",
  "event": "candidate_stage_changed",
  "newStage": "Interview Scheduled",
  "permissions": [
    "candidate.view",
    "candidate.edit",
    "task.create"
  ]
}
```

## OrkaFin process

```text
1. Verify user identity.
2. Confirm the user can view the candidate.
3. Confirm the user can create tasks.
4. Retrieve candidate context.
5. Retrieve Orka ATS workflow rules.
6. Check recent user behavior.
7. Detect that this user normally assigns interview tasks to Daniel.
8. Prepare a recommendation.
9. Request confirmation.
10. Send the approved action to Orka Task.
11. Record the action and result.
```

## OrkaFin output

```text
John Smith has been moved to Interview Scheduled.

You normally create an interview-preparation task at this stage and assign it to Daniel.

Would you like me to prepare that task?
```

## User confirmation

```text
Yes.
```

## Action preview

```text
Task: Prepare interview for John Smith
Assignee: Daniel
Due date: July 18, 2026

[Confirm] [Edit] [Cancel]
```

## Final output

```text
The interview-preparation task was created and assigned to Daniel.
```

---

# 21. Data Storage Strategy

## Prototype stage

The prototype may use:

- Google Sheets for feature catalogs.
- Google Sheets for event logs.
- Google Sheets for user roles and preferences.
- Google Drive or Docs for help content.
- Apps Script Properties for non-sensitive configuration.
- Apps Script web apps and server functions for integration.

This is acceptable for a limited internal pilot.

## Production stage

As data volume, concurrency, security requirements, and cross-app complexity increase, move central OrkaFin data to:

- Firestore or Cloud SQL.
- Cloud Storage for structured knowledge assets.
- Cloud Logging for system logs.
- Secret Manager for credentials.
- Pub/Sub or Cloud Tasks for background processing.

Do not keep the permanent production architecture dependent on one giant Google Sheet.

---

# 22. Prototype Versus Production

## Prototype

Suitable characteristics:

- One pilot application.
- Small internal user group.
- Basic text assistant.
- Feature guidance.
- Read-only app questions.
- Basic event tracking.
- Simple recommendations.
- Limited Gemini integration.
- Google Sheets-based metadata.

Apps Script is acceptable here.

## Production

Required characteristics:

- Multiple Orka applications.
- Central permission-aware intelligence.
- Strong auditing.
- Reliable APIs.
- Structured event storage.
- Cross-app workflows.
- Higher concurrency.
- Error monitoring.
- Background processing.
- Versioned schemas.
- Secure secrets.
- Scalable AI orchestration.

A Google Cloud backend is recommended here.

---

# 23. Recommended Development Plan

## Phase 0 — Foundation

- Confirm OrkaFin V1 scope.
- Select the first pilot application.
- Define the first target user.
- Define the first ten questions OrkaFin must answer.
- Define explicit V1 non-goals.
- Create a feature catalog.
- Create a page metadata catalog.
- Define user roles and permissions.
- Define the event schema.
- Define the action catalog.
- Define audit log requirements.

## Phase 1 — Orka ATS Guidance Pilot

Recommended first pilot: Orka ATS.

Build:

- OrkaFin panel inside Orka ATS.
- Current-user detection.
- Current-page context.
- Candidate context.
- Read-only Orka ATS functions.
- App feature knowledge.
- Step-by-step help.
- Safe fallback responses.
- Feedback controls.

V1 should not perform sensitive actions.

## Phase 2 — Recommendations

Add:

- Meaningful event logging.
- Usage pattern detection.
- Unused-feature recommendations.
- Next-application recommendations.
- User preference controls.
- Recommendation feedback.
- Recommendation frequency limits.

## Phase 3 — Approved Actions

Add:

- Task creation.
- Task assignment.
- Candidate-stage changes.
- Feedback requests.
- Meeting preparation.
- Confirmation screens.
- Action validation.
- Audit logs.
- Failure handling.

## Phase 4 — Cross-App Intelligence

Add:

- Standard adapters across Orka apps.
- Cross-app context.
- Shared user journey.
- Workflow recommendations.
- Organizational memory.
- Multi-app summaries.

## Phase 5 — Full Orka OS Companion

Add:

- Advanced automation.
- Long-term user preferences.
- Proactive productivity nudges.
- Voice input.
- Richer summaries.
- More sophisticated cross-app agent workflows.

---

# 24. Non-Goals and Guardrails

OrkaFin should not:

- Become a generic public chatbot.
- Replace all Google Workspace tools.
- Replicate Gemini features unrelated to Orka OS.
- Read every Google Sheet directly.
- Ignore application ownership.
- Bypass permissions.
- Reveal private projects.
- Invent Orka features.
- Execute sensitive actions without confirmation.
- Track every keystroke.
- Store unnecessary personal or sensitive data.
- Automatically retrain itself after every user action.
- Depend permanently on a single spreadsheet.
- Mix prototype shortcuts with production architecture without a migration plan.

---

# 25. Personalization Strategy

Early personalization should use:

- User preferences.
- Event history.
- Repeated behavior detection.
- Accepted and rejected recommendations.
- Workspace and role context.
- Saved defaults.
- Rule-based recommendation logic.
- Retrieval of approved organization knowledge.

Early personalization should not require continuous model retraining.

Example:

```text
The last seven IT tasks created by this user were assigned to Lassia.
```

OrkaFin may suggest:

```text
Would you like me to assign this IT task to Lassia?
```

The user must still be able to reject or change the suggestion.

---

# 26. Recommendation Quality Rules

Recommendations should be:

- Relevant to the current task.
- Based on approved features.
- Permission-safe.
- Explainable.
- Easy to dismiss.
- Rate-limited.
- Sensitive to user preferences.
- Measured for acceptance and rejection.

Recommendations should not:

- Interrupt the user constantly.
- Promote unrelated Orka applications.
- Repeat after repeated rejection.
- Suggest actions the user cannot perform.
- Claim nonexistent capabilities.

---

# 27. Security Rules

The following are mandatory:

- Server-side identity verification.
- Server-side permission checks.
- No trust in client-submitted roles.
- Least-privilege access.
- No unrestricted OrkaFin access to all application data.
- All sensitive actions require confirmation.
- Admin actions require stronger authorization.
- Private projects remain private.
- Application-specific validation remains in the application.
- Secrets must not be stored in frontend JavaScript.
- API keys must not be exposed in Apps Script HTML.
- Audit logs must cover important actions.
- Responses must avoid exposing unauthorized data.
- Prompt injection from documents or user content must not override system permissions.

---

# 28. Failure Behavior

OrkaFin must fail safely.

Examples:

## Unknown feature

```text
I could not find an approved Orka feature that supports this request.
```

## Missing permission

```text
You do not have permission to access this candidate.
```

## Application failure

```text
The task could not be created because Orka Task returned an error. No changes were made.
```

## Unverified identity

```text
Your account identity could not be verified. Please reopen the application through your PROJXON Workspace account.
```

## Missing context

```text
I cannot determine which candidate you are referring to. Select a candidate and try again.
```

No silent failure and no fabricated success message.

---

# 29. Success Metrics

Possible product metrics:

- Percentage of user questions answered correctly.
- Reduction in training or support requests.
- Time saved completing common workflows.
- Feature recommendation acceptance rate.
- Next-app adoption rate.
- Percentage of recommendations dismissed.
- Number of hallucinated feature reports.
- Permission-safety test pass rate.
- Action success rate.
- Action rollback or correction rate.
- User satisfaction.
- Number of repetitive workflows converted into approved automations.

The system should optimize for useful outcomes, not chatbot message volume.

---

# 30. Required Team Decisions

Before production development, the team must decide:

## Product

- What is the exact V1 scope?
- Which Orka application is the pilot?
- Who is the first target user?
- What are the first ten user questions?
- What actions are explicitly out of scope?

## Data

- Where will feature catalogs live?
- Where will help content live?
- What events will each app log?
- What information should not be collected?
- How long should events and audit logs be retained?

## Security

- What data can OrkaFin access?
- Which applications can users disable?
- Which actions require confirmation?
- Which actions require admin approval?
- How are project privacy rules represented?

## Engineering

- Which parts remain in Apps Script?
- When does the central backend move to Cloud Run?
- Which database will store events and audit logs?
- Which AI model and retrieval approach will be used?
- How will apps authenticate requests?
- How will API and schema versions be managed?

## UX

- How will the OrkaFin panel appear?
- Which suggested prompts appear first?
- How often can OrkaFin make proactive suggestions?
- How can users dismiss or disable recommendations?
- How will confirmation previews work?

---

# 31. Final Architecture Principles

Every future OrkaFin design must follow these principles:

1. OrkaFin is the intelligence layer, not the owner of every app's data.
2. Each Orka app remains responsible for its own data and business rules.
3. Apps Script remains valid for current Orka apps and the initial pilot.
4. A scalable Google Cloud backend should support the production intelligence layer.
5. Google Workspace identity is the authentication foundation.
6. Orka permissions determine what users can see and do.
7. OrkaFin receives controlled context, not unrestricted database access.
8. Meaningful events should be logged; keystrokes should not.
9. Feature and action catalogs must be explicit and versioned.
10. Sensitive actions require confirmation.
11. Important actions require audit logs.
12. Recommendations must be relevant, explainable, dismissible, and permission-safe.
13. OrkaFin must not invent features or fake successful actions.
14. The system should begin with guidance before automation.
15. The first pilot should prove one application end-to-end before connecting the whole ecosystem.
16. Prototype shortcuts must not become permanent production architecture accidentally.
17. Security, privacy, permissions, and auditability are core product features.
18. The visible chat panel is only the interface; the real product is the data, permissions, knowledge, APIs, events, and action infrastructure beneath it.

---

# 32. One-Sentence System Summary

OrkaFin is a permission-aware AI agent inside the Google Workspace-based Orka OS ecosystem that receives controlled context from Apps Script applications, provides grounded guidance and recommendations, and later performs confirmed actions through each application's approved adapter or API.
