# Architecture and pilot plan

## Design decision

Clinical text has one source: the approved structured case. A local or optional model router returns fact identifiers. The engine independently validates the identifiers, enforces disclosure conditions and copies the exact answer. A faculty-only fact never enters learner encounter projections or learner exports. This is an evidence-preservation design, not a proof of clinical correctness.

The case schema carries the facts and routing phrases; the engine contains no branches on seed patient names, case titles or diagnoses. New cases do not require Python or JavaScript changes. The stored draft and approved publication are separate. Each encounter snapshots an approved version and retains its hash even when the faculty later publishes another version.

## Storage model

`cases`: current draft, draft revision, last publication, publication revision, reviewer metadata and content hash.

`encounters`: owner, case ID, immutable case snapshot, snapshot hash/revision, encounter state, encounter revision and optional parent attempt.

`artifacts`: immutable attachment bytes, case/fact association, filename, type and SHA-256 hash.

`audit`: action, actor, timestamp, payload, prior hash and event hash. This is a local consistency check, not an append-only externally anchored ledger.

Sessions and login-attempt limits are in server memory. A server restart clears anonymous session ownership and local access tokens, not database records. Faculty review can still reach saved encounters. This is an explicit prototype tradeoff.

## Concurrency and boundaries

Turn processing first reads an authorized snapshot. Optional network routing runs outside the SQLite write transaction. The commit phase rechecks the encounter revision and idempotency key; stale writes fail and duplicate retries do not create another turn. Publication and attachment changes are transactional. Learner views are constructed on the server, rather than sending an answer key and hiding it with CSS.

The endpoint layer rejects unauthenticated faculty actions, uses an HttpOnly SameSite cookie, checks a per-session CSRF token and Origin on writes, limits request size and restricts serving to localhost. Uploaded files are never served as executable application resources. All authored and learner text is escaped before insertion into the UI. These are targeted prototype controls, not a comprehensive penetration test.

## Main API routes

GET `/api/bootstrap`, `/api/cases`, `/api/history`, `/api/encounters/{id}`.

POST `/api/encounters` to start; `/api/encounters/{id}/turn`, `/finish`, `/retry` for the encounter lifecycle. Turns require the current revision and an idempotency key.

GET `/api/encounters/{id}/export` after completion. Student exports contain a redacted case view with its own hash; the full approved-case hash remains a separate version identifier.

POST `/api/login`, `/api/logout` for the demo faculty gate.

Faculty-only GET/POST `/api/faculty/cases`, GET/POST `/api/faculty/cases/{id}`, POST suffixes `/approve` and `/upload`.

Faculty-only `/api/faculty/validate`, `/api/faculty/analytics`, `/api/faculty/audit`, `/api/faculty/history` and `/api/encounters/{id}/review`.

GET `/api/artifacts/{id}?encounter={id}` requires either faculty access or the owning learner encounter having disclosed the attachment’s linked fact.

## Evaluation that would substantiate the project

### Technical workflow validation — implemented and executed

Finite regression checks for unseen case creation, active-version isolation, source-only clinical text, unknown-detail abstention, scripted gates, record disclosure, session isolation, CSRF, upload boundaries, idempotency, concurrency, debrief gating, snapshot exports and audit mutation. The browser workflow additionally checks responsive layout and real UI authoring.

### Routing evaluation — proposed, not completed as an independent study

Have a faculty member and learner jointly author a blinded set of at least 100 questions spanning three unseen cases. Include synonyms, vague references, follow-up pronouns, compound questions, leading negatives and unsupported requests. Annotate which facts should be selected, whether abstention is correct, and any disclosure restrictions. Separate natural-language routing misses from faculty source omissions. Compare local routing and a fixed configured model. Lock the dataset before tuning and retain a new held-out set for final reporting.

### Feedback agreement — proposed

Recruit two independent faculty raters to annotate the same synthetic transcripts, without viewing the system output. Compare the system’s fact-elicitation records and communication observations with their judgments. Resolve rubric ambiguity separately from software defects. Do not report reliability statistics without the actual annotated dataset and an appropriate analysis plan.

### User testing — proposed

A small initial usability pilot could involve 3 faculty authors and 8–12 students, subject to local institutional requirements. Each faculty member authors a new synthetic case; students complete two practice encounters. Observe time to publish, authoring mistakes, routing failures, source-inspection behavior and whether the debrief is understandable. This sample is for finding workflow problems, not establishing effectiveness.

For a later educational evaluation, compare a practice condition against an appropriate comparator and assess performance on an unseen case. Predefine endpoints and account for repeat-case familiarity. Improved scores on the same practiced case alone do not show clinical transfer.

### Go/no-go criteria — proposed acceptance criteria, not measured outcomes

A new reviewed case starts without code changes; an unknown value is never rendered as a generated clinical answer; hidden facts never appear in an active learner payload; no unauthorized user can retrieve another learner’s record; critical omissions remain explicit; every scored fact points to an actual disclosure turn. Before model-enabled judging, independently check at least 30 representative semantic questions and demonstrate timeout/fallback behavior.

## Priorities before the event demonstration

Spend the remaining time on one genuinely faculty-authored case, semantic routing verification with your own credentials, a rehearsed live-demo path and a documented mentor critique. Avatar animation, physiological modeling, voice, automated image interpretation, EMR integration and high-stakes grading are outside this release. Do not present them as implemented.

## Primary implementation references

OpenAI, “Structured model outputs,” consulted 9 October 2026 (Eastern): strict output schema and explicit refusal handling. https://developers.openai.com/api/docs/guides/structured-outputs

Python documentation, “http.server,” consulted 9 October 2026 (Eastern): the standard-library server is not recommended for production. https://docs.python.org/3/library/http.server.html

The supplied TwinVerse Challenge 1 slide is the project brief. Public event FAQ text did not establish detailed current submission rules in this review; organizer confirmation is required.
