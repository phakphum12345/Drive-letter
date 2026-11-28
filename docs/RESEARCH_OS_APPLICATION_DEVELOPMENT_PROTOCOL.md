# Research OS — Application Development Protocol

**Protocol ID:** ROS-APP-DEV-001  
**Version:** 1.0.0  
**Skill key:** `application_development`  
**Domain:** Engineering  
**Status:** Initial governed protocol  
**Applies to:** Web, mobile, desktop, API/backend, CLI, cross-platform and internal business applications

## 1. Purpose

Provide one repeatable, technology-neutral method for taking an application from an idea to a secure, tested, deployable, supportable product. The protocol applies to new applications, major features, migrations, modernization and maintenance.

The protocol is a planning and engineering skill. It does not itself grant permission to access accounts, modify production data, deploy, publish, approve a release, merge code or execute privileged operations. Those actions remain subject to the existing Research OS identity, policy, approval and execution boundaries.

## 2. Governing lifecycle

Every work item follows:

`DISCOVER → DEFINE → DESIGN → PLAN → IMPLEMENT → VERIFY → RELEASE → OPERATE → IMPROVE`

Repository work additionally follows the required change-control sequence:

`READ → ANALYZE → MODIFY → TEST → AUDIT → MERGE → VERIFY → FOLLOW-UP`

Rules:
- Read the existing repository, contracts, tests, architecture and user-facing behavior before proposing changes.
- Preserve existing data, behavior, compatibility and user workflows unless an approved requirement explicitly changes them.
- Do not start implementation while critical requirements, ownership, data classification or acceptance criteria remain unknown.
- Make small, reviewable changes with traceable evidence.
- Never report a test, review, deployment or release as successful without authoritative evidence.
- Never merge when a required check is failing, pending or missing.
- Separate unrelated work into separate branches and pull requests.
- Record assumptions, decisions, risks, blockers and deferred work.

## 3. Application component model

An application is assessed across these components. Mark each as **Required**, **Conditional** or **Not applicable**, with a reason.

| Component | What must be designed or verified |
|---|---|
| Product definition | Problem, target users, use cases, scope, non-goals, value and success measures |
| Requirements | Functional requirements, quality attributes, constraints, acceptance criteria and priorities |
| User experience | User journeys, navigation, information architecture, screen states, responsive behavior and accessibility |
| Presentation layer | Web/mobile/desktop UI, design system, localization, input validation and error feedback |
| Application/domain layer | Business rules, workflows, state transitions, validation and domain models |
| API/service layer | Contracts, versioning, authentication, authorization, rate limits, idempotency and error semantics |
| Data layer | Data model, ownership, storage, retention, encryption, migrations, backup and recovery |
| Identity and access | Authentication, sessions, roles, permissions, tenant/profile isolation and revocation |
| Integration layer | External APIs, OAuth, webhooks, queues, files, providers and failure handling |
| Runtime/platform | Supported OS/browser/device, packaging, configuration, dependencies and resource limits |
| Security and privacy | Threat model, secrets, least privilege, input/output safety, audit and privacy controls |
| Reliability | Offline/online behavior, retries, timeouts, concurrency, recovery and graceful degradation |
| Observability | Structured logs, metrics, traces, health/readiness, alerts and correlation IDs |
| Quality engineering | Unit, component, integration, contract, UI, accessibility, performance and end-to-end tests |
| Delivery and release | CI, artifacts, signing, versioning, release gates, rollout, rollback and provenance |
| Operations and support | Runbooks, support ownership, incident handling, service objectives and maintenance |
| Documentation | User guide, developer guide, API/schema docs, architecture decisions and change notes |

## 4. Phase gates and required outputs

### Gate 0 — Intake and discovery

Collect:
- Problem statement and intended outcome.
- User groups, actors and operating environment.
- Application type and target platforms.
- Existing repository, deployed product, integrations and constraints.
- Data categories, sensitivity, ownership and retention expectations.
- Known risks, deadlines, budget/resource constraints and dependencies.

Outputs:
- Intake brief.
- Current-state inventory.
- Stakeholder and actor map.
- Assumption, dependency and risk register.

Exit criteria: the problem, users, system boundary and decision owner are clear.

### Gate 1 — Requirements and acceptance

Define:
- Functional requirements by user journey.
- Non-functional requirements: security, privacy, accessibility, performance, availability, scalability, portability and maintainability.
- Supported devices, OS/browser versions and network conditions.
- Data inputs, outputs, sources, ownership, retention and deletion behavior.
- Failure, empty, loading, permission-denied and recovery states.
- Acceptance criteria written so they can be tested.
- Explicit exclusions and deferred requirements.

Outputs:
- Requirements specification.
- Use-case/user-story map.
- Acceptance-test matrix.
- Prioritized scope and traceability IDs.

Exit criteria: every in-scope requirement has an owner, priority and verifiable acceptance criterion.

### Gate 2 — UX and interaction design

Design:
- Information architecture and navigation.
- Primary and alternate user journeys.
- Wireframes or screen specifications.
- Loading, empty, success, error, offline and unauthorized states.
- Keyboard, screen-reader, contrast, focus and touch accessibility.
- Responsive layouts and platform conventions.
- Localization, time zones, dates, numbers and text expansion where relevant.

Outputs:
- User-flow diagrams.
- Screen inventory and interaction specifications.
- Design-system/component mapping.
- Accessibility and localization checklist.

Exit criteria: critical journeys can be reviewed end-to-end before implementation.

### Gate 3 — Architecture and technical design

Define:
- System context and trust boundaries.
- Component/module responsibilities and dependency direction.
- Runtime and deployment topology.
- Domain entities, state transitions and data ownership.
- API contracts, schemas, error model and versioning.
- Identity, authorization and tenant/profile boundaries.
- External integrations and provider abstraction where appropriate.
- Caching, queues, concurrency, retries, timeouts and idempotency.
- Migration, backup, restore and rollback strategy.
- Architecture decisions with alternatives and trade-offs.

Outputs:
- Architecture diagram.
- Component and data-flow diagrams.
- API/data contracts.
- Threat model.
- Architecture Decision Records (ADRs).
- Migration and rollback plan.

Exit criteria: critical interfaces, trust boundaries, data flows and failure modes are reviewed.

### Gate 4 — Implementation planning

Break the work into independently reviewable changes:
- Work breakdown structure and dependency graph.
- Milestones, owners and estimated effort.
- Repository/file impact map.
- Test plan and test data strategy.
- CI/build requirements.
- Feature flags and compatibility strategy.
- Rollback and recovery tasks.

Exit criteria: each change has scope, acceptance criteria, tests and a review path.

### Gate 5 — Implementation

Engineering rules:
- Inspect the relevant source and tests before editing.
- Follow existing conventions and reuse established components.
- Keep business logic separate from UI and infrastructure.
- Validate all untrusted input at boundaries.
- Enforce authorization on the server, not only in the UI.
- Avoid hard-coded secrets, environment-specific assumptions and hidden global state.
- Use safe, reversible data migrations.
- Preserve backward compatibility or document a deliberate breaking change.
- Add tests with each behavior change.
- Keep commits focused and document material decisions.

Outputs:
- Source changes.
- Updated tests.
- Updated schemas/contracts.
- Migration scripts where needed.
- Developer documentation and change notes.

### Gate 6 — Verification and quality

Required test layers, selected according to application type:
1. Static analysis, formatting, lint and type checks.
2. Unit tests for domain rules and edge cases.
3. Component/widget tests for UI states and interactions.
4. API/contract tests for request, response, authorization and compatibility.
5. Integration tests for databases, files, identity and external services.
6. End-to-end tests for critical user journeys.
7. Security tests: dependency audit, secret scan, authorization checks and threat-driven tests.
8. Accessibility and localization checks.
9. Performance, load, soak and resource tests where risk warrants them.
10. Platform-specific build, install, upgrade and uninstall tests.

Verification rules:
- Distinguish PASS, FAIL, BLOCKED, SKIPPED and NOT RUN.
- Record command, environment, version, commit SHA, result and relevant logs.
- A skipped test is not a pass.
- CI success does not substitute for a required real-device or production-like test.
- Test both success and denial/failure paths.
- Re-run impacted tests after the final code change.

Outputs:
- Test report and evidence links.
- Coverage or quality summary where available.
- Defect list and disposition.
- Security and accessibility findings.

Exit criteria: all required tests pass, no unresolved release-blocking defects remain, and evidence maps to the exact candidate SHA.

### Gate 7 — Release readiness and delivery

Verify:
- Release scope and version.
- Exact source commit and clean/known repository state.
- Required checks and approvals.
- Artifact contents, checksums, signatures and provenance.
- Configuration and secret provisioning.
- Database migration and compatibility.
- Deployment/rollout plan, health checks and rollback.
- Release notes, user documentation and support readiness.

Outputs:
- Release candidate manifest.
- Build and test evidence.
- Signed artifacts where applicable.
- Release notes and deployment/rollback runbook.

A release candidate, certification, deployment and public release are distinct states. Never infer one from another.

### Gate 8 — Operations and maintenance

Establish:
- Service health and readiness checks.
- Logs, metrics, traces and alert ownership.
- Support and incident escalation.
- Backup/restore drills and disaster recovery.
- Dependency and vulnerability updates.
- User feedback and defect triage.
- Data retention and deletion operations.
- Version support and deprecation policy.

Outputs:
- Operations runbook.
- Monitoring/alert definitions.
- Incident and maintenance records.
- Known limitations and follow-up backlog.

### Gate 9 — Improvement and closure

Compare outcomes with success measures. Record defects, user feedback, technical debt, lessons learned and follow-up work. Close only when deliverables, evidence, ownership and outstanding risks are documented.

## 5. Security, identity and privacy baseline

- Apply least privilege and deny by default.
- Separate authentication from authorization.
- Enforce permissions at every protected API/service boundary.
- Bind data access to the authenticated owner, tenant, profile and session.
- Never cross-contaminate Owner/User profiles or their memory, files, credentials or data.
- Keep secrets in approved secret storage; never commit or log them.
- Use TLS for network communication and encryption at rest where required.
- Validate file uploads, MIME types, size, paths and content.
- Protect against injection, XSS, CSRF, SSRF, insecure deserialization and dependency compromise as applicable.
- Define consent, purpose limitation, retention and deletion for personal data.
- Keep auditable records for privileged and sensitive actions.
- Require explicit approval for destructive, financial, external or production-changing operations.

For Research OS specifically, preserve the existing architecture boundary:
**Identity → Role → Permission → Tools → Skills → Data Scope**.
Do not create a second identity/OAuth system, bypass the existing API/session boundary, or let a Skill grant itself tool, approval, execution, deployment or release authority.

## 6. Reliability and failure-handling baseline

For every external dependency and stateful workflow, specify:
- Connection and operation timeouts.
- Bounded retries with backoff and jitter.
- Idempotency and duplicate-request protection.
- Circuit breaking or controlled degradation where appropriate.
- Offline queue/reconciliation behavior where applicable.
- Conflict resolution and concurrency control.
- Clear user-visible error and recovery instructions.
- Safe cancellation and cleanup.
- Data consistency and partial-failure handling.

Never silently switch to a mock provider or report simulated output as a real operation.

## 7. Application-type profiles

Use the common lifecycle, then add the relevant profile:

- **Web:** browser compatibility, responsive UI, CSP, CORS, session/cookie security, SEO where relevant.
- **Mobile:** permissions, lifecycle/background behavior, secure local storage, deep links, push notifications, store signing and real-device testing.
- **Desktop:** installer/update/uninstaller, code signing, OS integration, filesystem permissions, crash recovery and clean-machine testing.
- **API/backend:** OpenAPI/schema contract, auth scopes, rate limiting, idempotency, migrations, observability and load tests.
- **Data/AI application:** data lineage, evaluation sets, model/provider boundaries, prompt-injection defenses, output validation, cost/latency budgets and human review.
- **Offline-first application:** local persistence, sync protocol, conflict policy, retry queue, clock/time-zone handling and recovery after interrupted sync.

## 8. Required project artifacts

Each project should create or update the applicable items:

```text
project/
├── README.md
├── docs/
│   ├── product-brief.md
│   ├── requirements.md
│   ├── user-flows.md
│   ├── architecture.md
│   ├── data-model.md
│   ├── api-contract.md
│   ├── threat-model.md
│   ├── adr/
│   ├── test-plan.md
│   ├── release-runbook.md
│   └── operations-runbook.md
├── src/
├── tests/
│   ├── unit/
│   ├── component/
│   ├── integration/
│   ├── contract/
│   └── e2e/
├── migrations/
├── scripts/
└── .github/workflows/
```

This is a reference structure, not a mandate to duplicate files or restructure a mature repository. Reuse existing equivalents and preserve established layout.

## 9. Definition of Done

An application change is complete only when:
- [ ] Scope and acceptance criteria are approved.
- [ ] Existing architecture and behavior were inspected.
- [ ] Design and data/API contracts are updated where needed.
- [ ] Identity, authorization, privacy and threat boundaries are verified.
- [ ] Implementation is complete and reviewed.
- [ ] Required automated and manual tests pass.
- [ ] Build/package is tied to the exact source SHA.
- [ ] Release, migration and rollback plans are ready.
- [ ] Documentation and operational ownership are updated.
- [ ] Known limitations and follow-up work are recorded.
- [ ] Merge/release/deployment status is verified from the authoritative system.

## 10. Research OS skill contract

The `application_development` skill:
- Helps plan, inspect, design, implement and verify application work.
- Produces phase plans, checklists, architecture outlines, test matrices and release-readiness reviews.
- Must ask one focused clarification when a critical requirement is missing.
- Must surface assumptions and distinguish evidence from inference.
- Must respect the active user identity and current authorization scope.
- Must not perform privileged side effects merely because this skill was selected.
- Must defer approval, tool execution, Git mutation, deployment and release to their existing governed capabilities.
- Must not mutate Core Skills or promote learned skills automatically.

## 11. Evidence and versioning

Every protocol execution should record:
- Protocol ID and version.
- Project/repository identifier and target platform.
- Request/issue identifier and correlation ID.
- Baseline and candidate commit SHA when repository work is involved.
- Completed gates, skipped gates and reasons.
- Test commands, environment, results and evidence references.
- Open risks, approvals and release disposition.

Evidence must be generated by the relevant test, CI, deployment or audit system. This document defines the method; it is not proof that a project has passed it.
