# Verity Encounter — judging demonstration

## Positioning

“Verity is a virtual patient encounter whose clinical voice belongs to the faculty author, not to the language model. Faculty creates a case, approves a version, and students practice an interview. Every disclosed clinical answer traces to that version, and feedback traces to the actual questions and responses.”

Use “local phrase routing” for the default release. Only call the optional model path live after actually configuring and testing it. Do not describe either path as a validated empathy assessor.

## Five-minute live sequence

**0:00–0:30 — Frame the problem.**

“The difficult part is not making a chatbot sound like a patient. It is controlling what the patient knows, what becomes visible when, and why a student receives a particular observation.”

**0:30–2:00 — Let a faculty judge author the proof.**

Open Patient Studio. Select New patient. Ask for a fictional patient and a distinctive fact nobody has hard-coded. Keep it small: an opening statement, two elicitable facts and one linked objective. Enter question phrases suitable for local routing, or use the tested semantic mode. Save and approve with a reviewer name. Mention that approval in this local prototype is a demo workflow action, not professional identity verification.

Example, only when the judge does not volunteer another case: Robin Vale, age 38; “My right wrist aches after work.” Distinctive preceding activity: “It started after I spent a weekend assembling wooden birdhouses.” Suggested phrases: “activity; what started; birdhouses.” Link the objective “Elicit the preceding activity.”

**2:00–3:00 — Run the unseen patient.**

Start the published case. Ask about the activity. Point to the exact approved response, source ID, progressive chart entry and pinned version hash. No source-code or server change occurred.

Then ask, “What is your ferritin?” The correct system behavior is not to invent a number or say it is normal. Show the explicit simulation note and the unchanged chart.

**3:00–4:00 — Show learning evidence.**

End the encounter. Show the objective and the exact turn in which the fact was elicited. Use the replay slider to return to turn zero. The chart should return to the opening information. Explain that rubric coverage is not a competence score.

**4:00–5:00 — Show the control that a chatbot alone does not provide.**

Use the existing fatigue fixture to show a scripted empathy gate, or show an attached synthetic report withheld until requested. State that the release tests cover version isolation, hidden-data projections, unauthorized actions, unknown values and malformed model responses. Finish with the validation plan, not a made-up claim of improved clinical outcomes.

## Strong close

“The judge created the patient. The faculty-authored case supplied the answers. The transcript supplied the feedback evidence. Our next validation is whether independent faculty agree with those observations across unseen cases.”

## Questions to be ready for

**Is this just a prompt wrapper?** The case lifecycle, immutable snapshot, disclosure engine, evidence projection, upload gating and debrief are deterministic application components. The optional model can choose IDs but cannot write clinical answers.

**Can it still get something wrong?** Yes. The source can be incorrect, routing can select a wrong topic, and the text checklist can misread communication. Exact provenance does not solve those problems. We separate and test them.

**What happens when the internet fails?** Local mode needs no network after Python is available. In semantic mode, a provider failure falls back to phrase routing and the UI labels that change. Natural-language coverage may decrease.

**Can the student game it?** The checklist is explicitly formative and gameable; scripted phrases are not proof of empathy. Critical gaps remain visible, but the prototype does not claim examination integrity or certification.

**How is the benefit measured?** Measure faculty authoring time, routing relevance and disclosure errors on unseen questions; compare evidence-linked observations against independent faculty judgments. Assess educational transfer separately on an unseen post-practice case.

**What is not ready?** Clinical validation, real model-call verification in this release, institutional identity, multi-user hosting, accessibility certification, privacy/compliance approval and educational effectiveness evidence.

## Submission discipline

Keep an accurate team contribution and development log. Verify the event’s current rules and AI-assistance policy before submission. Show only genuine test results. A supplied sample fixture is not a clinician-approved case merely because its workflow status is approved.
