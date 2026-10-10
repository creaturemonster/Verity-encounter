# Verity Encounter

Faculty-authored virtual patients, disclosure-controlled encounters, and evidence-linked formative feedback.

Built against the supplied **TwinVerse Challenge 1: The Virtual Patient Encounter** slide. This is a runnable **synthetic-data, single-machine prototype**, not a validated educational assessment or a production medical system.

## Start in one command

Requires Python 3.10 or newer with SQLite support. The release was tested on Python 3.13. No pip packages, Node build, database server, API key or internet connection are needed for the default application.

```bash
cd verity_encounter
python run.py
```

On macOS/Linux, use `python3 run.py` when `python` is unavailable. On Windows, `py run.py` is another option.

Open `http://127.0.0.1:8080` in a browser. The terminal prints a newly generated faculty passphrase. Select **Faculty access** and enter that passphrase to author and approve cases. The passphrase is a local demo access gate, not proof of faculty credentials.

An occupied port is handled with an explanatory error. Use `python run.py --port 8090` to choose another port. Ctrl+C stops the server.

## What is implemented

- Patient Studio: no-code profile, exact patient answers, question phrases, disclosure rules, prerequisite facts, communication gates, objectives, weights and faculty-marked critical elements.
- Separate save-draft and approve-version actions; structural validation, revision conflicts and immutable encounter snapshots.
- Four entirely fictional teaching fixtures. Their workflow approval is explicitly labeled **Demo fixture—not clinician reviewed**.
- Split-screen encounter: patient transcript and progressive chart. Unrevealed fact content is not returned in the learner projection.
- Fact-ID router with exact quotation of approved clinical text. Missing details are simulation notes, not invented denials.
- Uploads of synthetic PDF, PNG, JPEG and UTF-8 text reports; 2 MB limit, file signature checks, immutable storage and hashes. Materials are downloadable only after their linked fact is disclosed. Uploading changes the draft and requires reapproval.
- Objective-linked debrief, exact evidence turns, a transparent communication pattern checklist, critical omissions, replay slider and repeat attempts pinned to the same case version.
- Faculty annotations that do not rewrite the transcript; unmatched-question review queue; JSON evidence export. Learner exports redact faculty-only notes and distinguish the full-case hash from the exported-view hash.
- SQLite persistence, optimistic revision checks, idempotent turn submission, concurrent duplicate handling, session ownership, CSRF checks, role checks, escaped UI text and a local hash-linked audit log.

The engine is an **interview simulation**, not a physiological simulator. It does not diagnose, prescribe, interpret uploaded images, or certify clinical competence.

## The response contract

```
Learner question
  -> local phrase router OR optional model topic selection
  -> validate selected IDs (maximum two)
  -> enforce disclosure / prerequisites / scripted communication gate
  -> phrase a patient reply from only the permitted facts
  -> separate model call reviews grounding
  -> on any failure, show the approved wording instead
  -> record extracts stay exact
  -> update only the disclosed chart facts
  -> record evidence for later debrief
```

Topic selection does not write the answer. The wording call may rephrase permitted facts, and the review call can reject that rephrasing. A failed, refused, or ungrounded reply is replaced by the approved sentence. That does **not** prove the selected fact is relevant or the faculty source is correct. Question routing, case correctness and educational validity remain distinct evaluation problems.

Local mode is explicitly labeled **Local phrase routing**. It is not an LLM and can miss paraphrases, pronouns and context-dependent questions. It matches case-author-defined whole phrases. Broad prompts do not automatically disclose an entire history.

## Optional semantic routing

An OpenAI Responses API adapter is included. Topic selection uses a strict JSON schema; the server independently rejects invalid IDs and checks disclosure rules before any wording is requested. A second call then phrases a reply from the permitted lines, and a third call reviews grounding. Provider errors, malformed outputs, refusals, failed grounding, and timeouts keep the approved wording. Record extracts are not rewritten. Topic-selection failure falls back to the local router.

Set a model identifier available to your own API account; no model availability or pricing is assumed. Enable external routing explicitly:

```bash
# macOS / Linux
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="your-supported-model-id"
python run.py --semantic
```

```powershell
# Windows PowerShell
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_MODEL="your-supported-model-id"
py run.py --semantic
```

Topic selection sends the current question, up to two recent learner questions, topic labels and routing phrases. It does not send patient answers. The wording call sends only the facts permitted for that turn, the patient’s name, age and pronouns, and a short slice of the already disclosed transcript. The grounding call sends the draft reply and those same permitted lines. Unrevealed answers, faculty notes and attachment bytes are not included. `store=false` is requested; do not interpret that as a comprehensive privacy/compliance guarantee. Only synthetic information is permitted here. Calls may incur charges under the API account.

**No live provider call was made in the release evaluation.** Adapter payload, refusal, malformed-response, timeout and fallback behavior were tested with mocks. Confirm model compatibility, external processing terms and routing performance before calling the live-model path demonstrated or validated.

## Testing and evidence

```bash
python -m unittest discover -s tests -v
```

The included release run contains **115 passing automated engine/service/HTTP/provider-contract tests**. This includes a real in-process HTTP server; it is not merely syntax checking. See `evidence/unittest_results.txt`.

An additional **34 Chromium UI workflow checks** passed. Because this evaluation environment blocks Chromium navigation to localhost, the shipped HTML/CSS/JS was rendered in an offline browser document; fetch was forwarded through a bridge to the real local HTTP server with its cookie jar. This checked authoring, approval, an unseen case, uploads, encounters, replay, retry, mobile layout and escaped HTML. It did not test native browser networking, native download dialogs, other browsers or production deployment. See `evidence/browser_results.json`.

The optional browser test requires Playwright and Chromium. Neither is an application runtime dependency:

```bash
python tests/browser_smoke.py
```

Set `CHROMIUM_PATH` when the executable is not discoverable. Captured interface images are in `evidence/`. Automated tests are finite checks, not a universal security proof or a competition ranking.

## Five-minute demonstration

Start with a genuinely new case, not only a canned scenario. Ask the faculty judge to provide a fictional name, presenting concern and distinctive fact. Author that case using **New patient**, link an objective, save and approve it. Run the published version immediately. Ask about the distinctive fact; show the exact source ID and version. Ask an unsupported question; show abstention. End the encounter and inspect the objective evidence. A detailed talk track is in `docs/JUDGE_DEMO.md` and the PDF guide.

To demonstrate attached records, use `samples/synthetic_lab_report.txt` or create your own fictional report. Attach it to a record-type fact, approve the revision, then request that record during a new encounter. Attaching to an already-running case does not retroactively change that encounter.

## Storage and access limits

The default database is `data/verity.sqlite3`. It stores case versions, synthetic encounter text, attachments and audit events **without application-level encryption**. It is created when the app starts and is not included in the release archive.

Anonymous learner identities use a server-memory session with a 12-hour cookie lifetime. After a server restart or session expiry, a learner receives a new anonymous identity and cannot retrieve old private encounters as that identity; faculty can still review saved records. Cases and encounter data themselves persist. For a fresh demonstration, use a different database path, for example `python run.py --db data/new-demo.sqlite3`.

The application binds to loopback and rejects non-local Host headers. Do not put it on a public server, tunnel it, or use it with real patient information. It is not an institutional login, class roster, HIPAA compliance program, encrypted records platform or hardened hosting stack. The hash chain is locally checkable but not externally anchored or tamper-proof. File signature checks are not malware scanning; do not upload untrusted real documents.

Before any institutional pilot, replace local sessions with institutional identity and authorization, add TLS, operational logging/monitoring, encrypted storage and backups, retention/deletion controls, upload sanitization/scanning, accessibility review, privacy review and clinician-approved cases. Move the HTTP layer to a production deployment stack. Separate provider latency from database writes; that separation is already implemented in the prototype.

## Eligibility and claims

The supplied challenge slide was the implementation brief. Current detailed judging weights, AI assistance rules, team requirements and code-eligibility rules were not independently verified from the public FAQ in this build. Confirm those with the organizers and keep an accurate record of code provenance and development timing. No submission, cloud deployment, account connection or repository publication was performed.

Do not claim a measured win probability, performance percentile, validated empathy score, educational effectiveness, physiological fidelity or zero clinical error. A defensible claim is: **the prototype renders clinical text only from the approved case and demonstrates no-code case creation with source-linked formative feedback**.

## Code map

`verity/engine.py` — generic case validation, routing, gates, exact answers and debrief.

`verity/service.py` — SQLite workflow, versioned snapshots, ownership, materials and audit.

`verity/server.py` — local HTTP interface, demo sessions, access and request checks.

`verity/provider.py` — optional external model ID router; no free-form clinical output.

`verity/seeds.py` — fictional teaching fixtures, separate from the generic engine.

`static/` — the shipped responsive browser interface; no bundled font files or external assets.

`tests/` — executable verification; `docs/` — demonstration, architecture and pilot materials.
