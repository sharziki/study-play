# Adaptive Study OS — implementation specification

**Status:** build-ready design for the existing `study-play` / Intellect repository  
**Primary learner:** incoming Purdue CS student pursuing advanced mathematics/CS, with Stanford transfer as an optional evidence-and-deadline track  
**System boundary:** Study OS owns learning state; Hermes orchestrates; Jarvis presents; Nova stores durable context and evidence

---

## 1. Product contract

### One-sentence thesis

Study OS converts authoritative course material and the learner's work into the single highest-value next attempt, then closes the loop:

> **teach → scaffolded checks → cold attempt → correction → spaced scheduling → transfer**

### Success condition

The system improves durable, transferable mastery while reducing planning overhead. It does **not** optimize time-in-app, card volume, cosmetic streaks, or transfer-admission speculation.

### Non-goals

- Replacing Purdue advisers, instructors, syllabi, official catalogs, or Stanford admissions/registrar guidance.
- Predicting admission probability or claiming that a Purdue course will transfer.
- Hard-coding course, major, degree, application, or transfer-credit requirements from model memory.
- Completing graded work on the learner's behalf.
- Letting an LLM own mastery, due dates, grades, calendars, relationship state, or evidence status.
- Treating scaffolded recognition, reading, or generated prose as proof of mastery.

### Product invariants

1. The learner can start a bounded, useful session in one action.
2. Unsupported retrieval never precedes teaching for an unlearned concept.
3. Mastery requires independent performance; durable mastery requires delayed retrieval and/or transfer.
4. Confidence is captured before reveal; latency is captured automatically.
5. Every answer, correction, requirement, deadline, and transfer-evidence claim retains provenance.
6. SQLite is authoritative for scheduling and mastery. Nova is authoritative for durable narrative context and evidence objects. Neither is silently reconstructed from model prose.
7. Hermes may propose actions; deterministic application code validates and commits them.
8. Jarvis shows outcomes, choices, and provenance—not agent plumbing.

---

## 2. Existing baseline and target architecture

The repository already has a strong local-first nucleus:

- `study.py`: SQLite schema, grounded generation, mastery observations, interval updates, review history, confidence/latency, and terminal UI.
- `web.py`: local API for dashboard, lessons, sessions, preview/commit, source intake, generation, and burying.
- `web_static/`: one-question-at-a-time web experience.
- Existing tables: `materials`, `questions`, `progress`, `reviews`, `lessons`, `lesson_progress`, `lesson_attempts`, `profile`.
- Existing safeguards: exact source quotes, no pre-submission answer exposure, deterministic recognition grading, learner rating for ambiguous recall, topic-linked transfer challenges, and forward-only migrations.

### Target topology

```text
                         ┌──────────────────────────┐
                         │ Jarvis Study workspace   │
                         │ Today / Course / Evidence│
                         └─────────────┬────────────┘
                                       │ typed HTTPS/localhost API
┌──────────────┐   intents/tools   ┌───▼─────────────────────────┐
│ Hermes       ├──────────────────►│ Study OS service           │
│ orchestrator │◄──────────────────┤ deterministic control plane│
└──────┬───────┘ receipts/events   └───┬──────────────┬──────────┘
       │                               │              │
       │ Nova MCP                      │ SQLite       │ calendar adapter
       ▼                               ▼              ▼
┌──────────────┐                ┌──────────────┐  ┌──────────────┐
│ Nova         │                │ study.db     │  │ Google/local │
│ context,     │                │ mastery, due,│  │ calendar     │
│ people,      │                │ attempts,    │  │ busy blocks  │
│ evidence     │                │ requirements │  │ + proposals  │
└──────────────┘                └──────────────┘  └──────────────┘
       ▲
       │ source/evidence pointers only; no mastery mirroring
       └─────────────────────────────────────────────────────────
```

### Authority matrix

| Domain | Authoritative store | May propose | May commit |
|---|---|---|---|
| Question/lesson content | Study DB + immutable source version | Hermes generator | Study validator only |
| Mastery, lapses, confidence, latency | Study DB event/history tables | nobody | Study scheduler only |
| Calendar busy time | Calendar provider | Hermes planner | user or pre-approved policy |
| Study-block plan | Study DB; mirrored event receipt in Jarvis | deterministic planner/Hermes | Study OS after conflict check |
| Course/degree/application requirements | versioned official-source records in Study DB | extraction agent | validator + user confirmation when ambiguous |
| People and relationship context | Nova | Hermes | Nova tools under normal approval rules |
| Transfer evidence artifacts | original file + hash; index in Study DB/Nova | Hermes summarizer | evidence service after provenance validation |
| Admissions interpretation | none | Hermes may surface questions for an adviser | never stored as fact without authoritative source |

---

## 3. Core domain model

### 3.1 Hierarchy

```text
learner
  ├── track                         # Purdue term, advanced math, research, transfer prep
  │    ├── course / campaign
  │    │    ├── source_version
  │    │    ├── assignment / exam
  │    │    └── concept ──prerequisite──► concept
  │    │          ├── lesson
  │    │          ├── question
  │    │          └── mastery_state
  │    └── requirement (source-versioned; never inferred)
  ├── study_session → attempts → reviews
  ├── calendar_block
  ├── person / interaction pointer (Nova slug)
  └── evidence_artifact → claim/evidence bundle
```

### 3.2 State machines

#### Concept learning stage

```text
unseen
  → teach
  → scaffolded_check
  → cold_attempt
  ├─ miss ─────────────► correction ─► short_retry ─► cold_attempt
  └─ pass ─────────────► spaced
spaced + delayed_pass ─► transfer
transfer + pass ───────► durable
any independent lapse ─► correction (mastery retained but reduced)
```

Rules:

- `teach` and `scaffolded_check` can unlock a cold attempt but cannot set `mastered`.
- A transfer question is always independent: no lesson text, hints, worked example, or answer-bearing context visible.
- A scaffolded miss stays on the same layer until corrected.
- A learner may request a diagnostic cold attempt to skip teaching; passing raises the stage, failing routes to teaching without penalty.
- Advanced learners skip redundant instruction after demonstrated cold mastery.

#### Artifact evidence status

```text
draft → captured → provenance_verified → included
                   └───────────────► disputed / superseded
```

#### Requirement status

```text
candidate → source_verified → user_confirmed (if ambiguous) → active
          └───────────────► stale → reverify
```

No scheduler logic may depend on `candidate` or `stale` requirements.

---

## 4. Persistence design

Use forward-only SQLite migrations. Keep current tables and rows. Add a `schema_migrations(version, applied_at)` table and migrate in transactions. Prefer new normalized tables over widening JSON blobs that scheduler code must query.

### 4.1 Additions to existing tables

```sql
ALTER TABLE materials ADD COLUMN source_type TEXT NOT NULL DEFAULT 'learner_note';
ALTER TABLE materials ADD COLUMN source_url TEXT;
ALTER TABLE materials ADD COLUMN source_version_id INTEGER REFERENCES source_versions(id);
ALTER TABLE materials ADD COLUMN trust_level TEXT NOT NULL DEFAULT 'learner_supplied';

ALTER TABLE questions ADD COLUMN concept_id INTEGER REFERENCES concepts(id);
ALTER TABLE questions ADD COLUMN support_kind TEXT NOT NULL DEFAULT 'answer_evidence';
ALTER TABLE questions ADD COLUMN generator_run_id INTEGER REFERENCES generation_runs(id);

ALTER TABLE reviews ADD COLUMN attempt_id TEXT;
ALTER TABLE reviews ADD COLUMN hint_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE reviews ADD COLUMN reveal_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE reviews ADD COLUMN grader_kind TEXT NOT NULL DEFAULT 'learner_or_deterministic';
```

`attempt_id` must receive a unique index when populated so retrying a POST cannot double-commit mastery.

### 4.2 New tables

```sql
CREATE TABLE tracks (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN
    ('term','course','advanced_math','research','transfer','general')),
  status TEXT NOT NULL DEFAULT 'active',
  goal TEXT NOT NULL DEFAULT '',
  starts_at TEXT,
  ends_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE courses (
  id INTEGER PRIMARY KEY,
  track_id INTEGER NOT NULL REFERENCES tracks(id),
  institution TEXT NOT NULL,
  official_code TEXT,                 -- nullable until source-verified
  title TEXT NOT NULL,
  term TEXT,
  syllabus_source_version_id INTEGER REFERENCES source_versions(id),
  status TEXT NOT NULL DEFAULT 'planned',
  UNIQUE(institution, official_code, term)
);

CREATE TABLE source_versions (
  id INTEGER PRIMARY KEY,
  canonical_url TEXT,
  title TEXT NOT NULL,
  publisher TEXT NOT NULL,
  source_kind TEXT NOT NULL CHECK(source_kind IN
    ('official_web','syllabus','assignment','exam','textbook','notes','solution_key','rubric','email','calendar','other')),
  retrieved_at TEXT NOT NULL,
  effective_at TEXT,
  content_hash TEXT NOT NULL,
  extracted_text TEXT NOT NULL,
  supersedes_id INTEGER REFERENCES source_versions(id),
  verification_status TEXT NOT NULL CHECK(verification_status IN
    ('pending','verified','failed','stale')),
  UNIQUE(content_hash)
);

CREATE TABLE concepts (
  id INTEGER PRIMARY KEY,
  course_id INTEGER REFERENCES courses(id),
  track_id INTEGER NOT NULL REFERENCES tracks(id),
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  knowledge_kind TEXT NOT NULL CHECK(knowledge_kind IN ('derivable','arbitrary','mixed')),
  importance REAL NOT NULL DEFAULT 1.0 CHECK(importance BETWEEN 0 AND 2),
  status TEXT NOT NULL DEFAULT 'active',
  UNIQUE(track_id, slug)
);

CREATE TABLE concept_edges (
  from_concept_id INTEGER NOT NULL REFERENCES concepts(id),
  to_concept_id INTEGER NOT NULL REFERENCES concepts(id),
  relation TEXT NOT NULL CHECK(relation IN ('prerequisite','part_of','contrasts','transfers_to')),
  source_version_id INTEGER REFERENCES source_versions(id),
  PRIMARY KEY(from_concept_id, to_concept_id, relation)
);

CREATE TABLE mastery_states (
  concept_id INTEGER PRIMARY KEY REFERENCES concepts(id),
  stage TEXT NOT NULL CHECK(stage IN
    ('unseen','teach','scaffolded_check','cold_attempt','correction','spaced','transfer','durable')),
  mastery REAL NOT NULL DEFAULT 0 CHECK(mastery BETWEEN 0 AND 1),
  stability_days REAL NOT NULL DEFAULT 0,
  difficulty REAL NOT NULL DEFAULT 0.5 CHECK(difficulty BETWEEN 0 AND 1),
  due_at TEXT NOT NULL,
  last_independent_at TEXT,
  last_transfer_at TEXT,
  independent_successes INTEGER NOT NULL DEFAULT 0,
  transfer_successes INTEGER NOT NULL DEFAULT 0,
  lapses INTEGER NOT NULL DEFAULT 0,
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE TABLE assessments (
  id INTEGER PRIMARY KEY,
  course_id INTEGER NOT NULL REFERENCES courses(id),
  kind TEXT NOT NULL CHECK(kind IN ('assignment','quiz','exam','project','reading','other')),
  title TEXT NOT NULL,
  due_at TEXT,
  weight_text TEXT,                    -- retain source wording; do not invent numeric weight
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  status TEXT NOT NULL DEFAULT 'active',
  UNIQUE(course_id, title, source_version_id)
);

CREATE TABLE assessment_concepts (
  assessment_id INTEGER NOT NULL REFERENCES assessments(id),
  concept_id INTEGER NOT NULL REFERENCES concepts(id),
  relevance REAL NOT NULL DEFAULT 1 CHECK(relevance BETWEEN 0 AND 1),
  provenance TEXT NOT NULL,
  PRIMARY KEY(assessment_id, concept_id)
);

CREATE TABLE requirements (
  id INTEGER PRIMARY KEY,
  track_id INTEGER NOT NULL REFERENCES tracks(id),
  category TEXT NOT NULL,
  requirement_text TEXT NOT NULL,      -- close quote or faithfully extracted statement
  source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
  source_locator TEXT NOT NULL,        -- heading/page/quote offsets
  status TEXT NOT NULL CHECK(status IN
    ('candidate','source_verified','user_confirmed','active','stale','superseded')),
  effective_at TEXT,
  expires_at TEXT,
  supersedes_id INTEGER REFERENCES requirements(id),
  created_at TEXT NOT NULL
);

CREATE TABLE study_sessions (
  id TEXT PRIMARY KEY,
  track_id INTEGER REFERENCES tracks(id),
  planned_minutes INTEGER NOT NULL,
  started_at TEXT,
  ended_at TEXT,
  mode TEXT NOT NULL CHECK(mode IN ('daily','exam','concept','assignment','diagnostic')),
  planner_version TEXT NOT NULL,
  queue_snapshot_json TEXT NOT NULL,
  completion_reason TEXT
);

CREATE TABLE attempt_events (
  id TEXT PRIMARY KEY,                  -- client-generated idempotency key
  session_id TEXT REFERENCES study_sessions(id),
  question_id INTEGER NOT NULL REFERENCES questions(id),
  concept_id INTEGER REFERENCES concepts(id),
  phase TEXT NOT NULL CHECK(phase IN ('scaffolded','cold','spaced','transfer')),
  response_text TEXT NOT NULL DEFAULT '',
  selected_choice INTEGER,
  confidence INTEGER NOT NULL CHECK(confidence BETWEEN 1 AND 5),
  latency_ms INTEGER NOT NULL CHECK(latency_ms >= 0),
  hint_count INTEGER NOT NULL DEFAULT 0,
  correctness TEXT NOT NULL CHECK(correctness IN ('correct','incorrect','ambiguous')),
  rating TEXT CHECK(rating IN ('again','hard','good','easy')),
  grading_method TEXT NOT NULL,
  created_at TEXT NOT NULL,
  committed_at TEXT,
  mastery_before REAL,
  mastery_after REAL
);

CREATE TABLE calendar_blocks (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  external_id TEXT,
  block_kind TEXT NOT NULL CHECK(block_kind IN
    ('class','study','deadline','office_hours','research','personal','buffer')),
  title TEXT NOT NULL,
  starts_at TEXT NOT NULL,
  ends_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('proposed','confirmed','cancelled','completed')),
  linked_type TEXT,
  linked_id TEXT,
  plan_version INTEGER NOT NULL DEFAULT 1,
  UNIQUE(provider, external_id)
);

CREATE TABLE people_links (
  id INTEGER PRIMARY KEY,
  nova_slug TEXT NOT NULL UNIQUE,
  relationship_kind TEXT NOT NULL CHECK(relationship_kind IN
    ('instructor','ta','advisor','peer','researcher','mentor','other')),
  display_name TEXT NOT NULL,
  consent_scope TEXT NOT NULL DEFAULT 'learner_only',
  last_interaction_at TEXT
);

CREATE TABLE interaction_plans (
  id INTEGER PRIMARY KEY,
  person_link_id INTEGER NOT NULL REFERENCES people_links(id),
  purpose TEXT NOT NULL,
  preparation_json TEXT NOT NULL,       -- learner's questions, evidence, desired outcome
  scheduled_block_id TEXT REFERENCES calendar_blocks(id),
  outcome_nova_slug TEXT,
  status TEXT NOT NULL CHECK(status IN ('draft','ready','completed','cancelled')),
  created_at TEXT NOT NULL
);

CREATE TABLE evidence_artifacts (
  id TEXT PRIMARY KEY,
  track_id INTEGER NOT NULL REFERENCES tracks(id),
  artifact_kind TEXT NOT NULL CHECK(artifact_kind IN
    ('graded_work','project','proof','code','research_note','poster','recommendation_context','reflection','transcript','other')),
  title TEXT NOT NULL,
  original_uri TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  source_version_id INTEGER REFERENCES source_versions(id),
  nova_slug TEXT,
  status TEXT NOT NULL CHECK(status IN ('draft','captured','provenance_verified','included','disputed','superseded')),
  UNIQUE(content_hash)
);

CREATE TABLE evidence_claims (
  id INTEGER PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES evidence_artifacts(id),
  claim_text TEXT NOT NULL,
  evidence_locator TEXT NOT NULL,
  claim_kind TEXT NOT NULL CHECK(claim_kind IN
    ('mastery','initiative','research','collaboration','impact','growth','other')),
  verification_status TEXT NOT NULL CHECK(verification_status IN
    ('pending','verified','rejected'))
);

CREATE TABLE outbox_events (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  published_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);

CREATE TABLE generation_runs (
  id INTEGER PRIMARY KEY,
  material_id INTEGER NOT NULL REFERENCES materials(id),
  generator TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  requested_count INTEGER NOT NULL,
  returned_count INTEGER NOT NULL DEFAULT 0,
  accepted_count INTEGER NOT NULL DEFAULT 0,
  persisted_count INTEGER NOT NULL DEFAULT 0,
  source_window_json TEXT NOT NULL,
  status TEXT NOT NULL,
  error TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
```

### 4.3 Indexes and constraints

```sql
CREATE UNIQUE INDEX ux_reviews_attempt_id ON reviews(attempt_id) WHERE attempt_id IS NOT NULL;
CREATE INDEX ix_mastery_due ON mastery_states(due_at, stage, mastery);
CREATE INDEX ix_attempt_concept_time ON attempt_events(concept_id, created_at);
CREATE INDEX ix_assessment_due ON assessments(due_at, status);
CREATE INDEX ix_calendar_time ON calendar_blocks(starts_at, ends_at, status);
CREATE INDEX ix_requirement_track_status ON requirements(track_id, status);
CREATE INDEX ix_outbox_unpublished ON outbox_events(published_at, created_at);
```

### 4.4 Compatibility bridge

Until every question has `concept_id`, create concepts from normalized `(campaign, topic)` pairs and backfill in one transaction. Existing `progress.mastery` remains operational during migration; `mastery_states` becomes authoritative only when a migration flag is set after parity tests compare both calculations on fixture history.

---

## 5. Deterministic learning engine

### 5.1 Evidence classes

| Phase | Counts toward mastery? | Max mastery effect | Scheduler behavior |
|---|---:|---:|---|
| Teach/read | No | 0 | unlock check only |
| Scaffolded check | Readiness only | small; cannot cross mastery threshold | retry missed layer |
| Cold independent attempt | Yes | primary | miss returns soon; pass expands interval |
| Delayed spaced attempt | Yes | primary | updates stability and due date |
| Novel transfer attempt | Yes | strongest evidence | required for `durable` on derivable concepts |

Hints, visible lesson text, answer reveal, collaboration, and retries in the same exposure window must reduce evidence class or mark the attempt scaffolded.

### 5.2 Attempt commit algorithm

All commits are transactional and idempotent by `attempt_id`.

```python
def commit_attempt(cmd, now):
    validate_question_and_phase(cmd)
    if exists(cmd.attempt_id):
        return prior_receipt(cmd.attempt_id)

    # Confidence must have been locked before answer reveal.
    assert 1 <= cmd.confidence <= 5
    assert cmd.latency_ms >= 0

    grading = deterministic_grade_or_ambiguous(cmd)
    if grading.is_ambiguous and cmd.learner_rating is None:
        return preview_without_commit(grading)

    state = lock_mastery_state(cmd.concept_id)
    observation = observation_score(
        correctness=grading.correctness,
        rating=cmd.learner_rating or grading.rating,
        phase=cmd.phase,
        confidence=cmd.confidence,
        latency_ms=cmd.latency_ms,
        target_latency_ms=question.target_latency_ms,
        hints=cmd.hint_count,
        prior_reveal=cmd.reveal_count > 0,
    )
    next_state = scheduler.update(state, observation, now)
    insert_attempt_event(...state, next_state...)
    update_mastery_state(version=state.version + 1)
    insert_compat_review_and_progress(...)
    insert_outbox_event('study.attempt_committed', ...)
    commit()
    return receipt(next_state)
```

Correctness dominates. Confidence and latency are bounded modifiers, never enough to turn a miss into mastery. An overconfident miss receives high remediation priority, not punishment.

### 5.3 Scheduler priorities

Build a candidate set larger than the requested session, calculate deterministic scores, then apply composition and adjacency constraints.

```text
priority =
  4.0 * overdue_pressure
+ 3.0 * (1 - mastery)
+ 2.5 * recent_lapse
+ 2.0 * overconfident_miss
+ 2.0 * assessment_urgency
+ 1.5 * prerequisite_blocker
+ 1.0 * transfer_due
+ 0.5 * freshness_need
- 2.0 * same_concept_recently_seen
- 1.0 * context_switch_cost_near_deadline
```

Definitions are pure functions with versioned constants:

- `overdue_pressure = clamp(hours_overdue / horizon_hours, 0, 1)`.
- `assessment_urgency` is nonzero only when a source-verified assessment links to the concept.
- `overconfident_miss` means confidence ≥ 4 and incorrect/again.
- `prerequisite_blocker` applies when the concept blocks an active, important downstream concept.
- `freshness_need` allocates a bounded amount of new material.

### 5.4 Session composition

Default 20-minute session target:

- 50–60% due/overdue independent reviews.
- 15–25% recent misses, especially overconfident misses.
- 10–20% new material, starting with teach/check when needed.
- 10–20% transfer/keep-alive.

These are queue constraints, not learning claims. Exact counts are derived from session length and available candidates. Never fabricate filler merely to hit a ratio.

Interleaving constraints:

1. Avoid adjacent same-concept items when another useful candidate exists.
2. Prefer method discrimination across related concepts.
3. Near an exam, reduce broad context switching but retain at least one interleaved discriminator.
4. Do not present the same prompt twice in one session.
5. Cap new concepts to prevent an unfinishable correction backlog.

### 5.5 Mastery promotion rules

Configurable, versioned defaults—not admission or course requirements:

- `unseen → teach` when prerequisites are sufficiently ready or the learner explicitly starts.
- `scaffolded_check → cold_attempt` after all checks are passed once.
- `cold_attempt → spaced` only after an independent good/easy result.
- `spaced → transfer` when the concept is due for application and prerequisites remain ready.
- `transfer → durable` only after at least one independent transfer success and one delayed independent success on derivable concepts.
- Arbitrary facts may become durable through delayed retrieval without forced “transfer.”
- A lapse reduces mastery/stability and schedules correction; it does not erase history.

Every state transition stores scheduler version and before/after values for replay.

---

## 6. Grounded content pipeline

### 6.1 Intake classes

- Official catalog/admissions/registrar page.
- Course syllabus and schedule.
- Assignment, rubric, problem set, exam guide, or released solution.
- Textbook/chapter/lecture notes.
- Learner notes and solved work.
- Email/calendar item.

Each intake becomes an immutable `source_version`. A changed URL creates a new version and marks dependent requirements for revalidation; it never overwrites the old evidence.

### 6.2 Trust and prompt-injection boundary

Imported content is data, never instructions. Model calls receive a delimited source window and no mutation tools. The model may propose:

- concepts and prerequisite edges;
- lesson fields;
- questions, choices, answers, explanations, difficulty, and source quotes;
- assessment metadata and requirement candidates;
- evidence-claim candidates.

It may not propose or mutate mastery, intervals, deadlines not present in the source, requirement status, grades, calendar confirmation, relationship facts, or evidence verification.

### 6.3 Question acceptance gate

A candidate is accepted only if:

1. It conforms to the exact JSON schema; array requests are batched to schema `maxItems`.
2. `source_quote` is an exact substring of the immutable source version and long enough to support the claim.
3. The answer is supported by the quoted source.
4. Choices are unique and the declared answer exactly matches the correct choice.
5. It has one identifiable concept and an allowed question kind.
6. It is not a duplicate/near-duplicate of an accepted prompt.
7. A problem-only source is not treated as an answer key. Such material may create an ungraded practice prompt, but no confident answer/explanation.
8. Transfer questions either remain directly source-grounded or are marked `constructed_application` and require a deterministic or human-verified solution before entering a scored queue.

Report `requested`, `returned`, `accepted`, and `persisted` separately.

### 6.4 Proof and code grading

- Multiple choice and exact structured outputs: deterministic.
- Numeric/algebraic outputs: deterministic normalization where safe; retain original response.
- Code: disposable sandbox + hidden/source-approved tests; never execute imported code on the host.
- Proofs and explanations: model may generate a rubric-aligned comparison, but the learner must self-rate unless a human-approved rubric supports a deterministic checklist.
- Ambiguity never silently commits.

---

## 7. Course, assignment, exam, and requirement ingestion

### 7.1 No-invention policy

The database ships with **zero asserted Purdue or Stanford requirements**. A requirement appears only after an official source is fetched/imported, versioned, and its exact locator is stored. Syllabi may define course obligations; only institution-authoritative sources may define degree, admission, or transfer-credit policy.

Seed the authority registry with URLs, not extracted claims:

- Purdue CS degree-requirement authority: `https://www.cs.purdue.edu/undergraduate/curriculum/bachelor.html`
- Stanford transfer-applicant authority: `https://admission.stanford.edu/apply/transfer/index.html`
- Stanford transfer eligibility authority: `https://admission.stanford.edu/apply/transfer/eligibility.html`
- Stanford undergraduate transfer-credit authority: `https://studentservices.stanford.edu/my-academics/earn-my-degree/undergraduate-degree-progress/test-transfer-credit/undergraduate`

These pages must be re-fetched at use time and treated as versioned sources. The UI shows retrieval time, effective date if stated, source locator, and a “verify with adviser/admissions” action. Stanford transfer admission and transfer credit remain separate tracks.

### 7.2 Syllabus ingestion workflow

1. Upload/fetch source; hash and version it.
2. Extract course identity, topics, assessments, dates, and source wording into `candidate` records.
3. Show a diff-style confirmation screen with exact quotes and locators.
4. Confirm only unambiguous syllabus facts; unresolved items become questions, not assumptions.
5. Build concepts and assessment links.
6. Generate a diagnostic, lessons, and questions under grounding gates.
7. Replan calendar proposals around verified due dates and existing busy blocks.

### 7.3 Assignment workflow

```text
assignment arrives
→ provenance/version capture
→ learner labels: graded / practice / solution available?
→ extract concepts and explicit due date
→ create readiness diagnostic
→ schedule learn/practice/review blocks
→ learner completes work outside answer-generating mode
→ post-submission correction + evidence capture
```

For graded work before submission, Study OS may explain concepts, ask Socratic questions, generate analogous practice, inspect learner-authored work against an instructor-permitted rubric, and find errors. It may not produce a submission-ready answer unless the user confirms the work is practice/open-solution and policy permits it.

### 7.4 Exam planning

Backward-plan from a source-verified exam time:

- reserve a final buffer before the exam;
- prioritize prerequisite blockers and high-importance weak concepts;
- schedule at least one cold mixed simulation when time permits;
- stop introducing low-value new material when correction debt would exceed available time;
- preserve sleep/personal blocks and expose conflicts rather than silently overbooking.

The planner returns proposals with reasons. Calendar writes require confirmation unless an explicit, bounded policy authorizes routine study blocks.

---

## 8. Calendar and daily planning

### Daily plan input

- confirmed calendar busy blocks;
- source-verified deadlines and exams;
- current concept due queue and correction debt;
- learner-selected available study windows and energy preference;
- unfinished confirmed blocks from the prior day.

### Deterministic block planner

1. Subtract busy time and protected buffers.
2. Score candidate objectives by due/mastery/assessment/prerequisite priority.
3. Pack 10/20/35/50-minute blocks; include setup and transition buffer.
4. Never schedule overlapping confirmed blocks.
5. Label each block with an objective, stop condition, and deep link to its queue.
6. Emit proposals; user confirms or a previously approved policy commits.
7. On missed blocks, replan remaining work without shame or streak penalty.

Example receipt:

```json
{
  "block_id": "blk_01...",
  "starts_at": "...",
  "ends_at": "...",
  "objective": "Cold mixed practice on source-linked concepts",
  "queue_id": "ses_01...",
  "reason_codes": ["exam_urgency", "prerequisite_blocker"],
  "status": "proposed",
  "conflicts": []
}
```

No personal-calendar detail is sent to a model when deterministic free/busy data suffices.

---

## 9. Office hours, research, and relationship support

### Principle

The system supports better human relationships; it does not automate intimacy, impersonate the learner, or manufacture recommendation narratives.

### Before office hours

Generate a one-page preparation packet from learner-owned attempts:

- the exact concept/problem source;
- what the learner tried;
- the earliest divergence or unresolved step;
- up to three specific questions;
- desired outcome;
- relevant assignment-policy warning.

No automatic email is sent. The learner edits and chooses what to share.

### After office hours

Hermes prompts for a 60-second capture: answer learned, follow-up promised, new source, and next action. Deterministic actions enter Study OS. Durable interaction context and a pointer to any notes enter Nova with provenance and the learner's consent.

### Research relationship workflow

1. Maintain an interest map of source-backed topics and completed work.
2. Surface relevant faculty/lab pages only as research leads, never as personal claims.
3. Prepare a genuine reading trail and questions before outreach.
4. Draft outreach from verifiable learner work; require learner review and send confirmation.
5. Track commitments and follow-ups, not “relationship scores.”
6. Capture research artifacts, feedback, and revisions as evidence with original timestamps.

Never infer private facts about instructors, rank people by usefulness, or fabricate familiarity.

---

## 10. Transfer evidence track

The optional Stanford track is an **evidence and deadline workspace**, not an admissions optimizer.

### Evidence bundles

Capture artifacts that already exist through real academic work:

- graded work and feedback;
- independently authored proofs/code/projects;
- research notes/posters/results;
- revision histories showing growth;
- collaboration context with consent;
- official transcript/report artifacts when the learner provides them;
- reflections linking artifacts to verified claims.

Each evidence claim must point to an immutable artifact and locator. “Strong,” “advanced,” or “impactful” remains a draft interpretation until supported by the artifact or external feedback.

### Evidence packet output

```json
{
  "packet_id": "evid_...",
  "purpose": "transfer_application_support",
  "as_of": "...",
  "artifacts": [{"id": "...", "hash": "...", "uri": "..."}],
  "claims": [{"text": "...", "artifact_id": "...", "locator": "...", "status": "verified"}],
  "gaps": ["..."],
  "requirements_snapshot": [{"id": 0, "source_version_id": 0}],
  "disclaimer": "Verify all current requirements and credit decisions with official offices."
}
```

The system must not distort course selection solely for transfer optics, encourage performative professor contact, or promise credit/admission outcomes.

---

## 11. Hermes, Jarvis, and Nova integration

### 11.1 Hermes role

Hermes is the conversational router and bounded cognitive worker. Expose Study OS as an MCP server or typed local tools:

```text
study.next_action(read-only)
study.create_session(plan)
study.get_session(read-only; no answers)
study.preview_attempt(no commit)
study.commit_attempt(idempotent mutation)
study.ingest_source(provenance required)
study.propose_calendar(read-only proposal)
study.confirm_calendar_block(approved mutation)
study.prepare_office_hours(read-only draft)
study.capture_evidence(provenance required)
study.requirements_snapshot(read-only)
```

Hermes must call read tools before proposing a plan, state uncertainty, and request approval at calendar, communication, or external-submission boundaries. Long generation runs become tracked jobs; no hidden subprocess state.

### 11.2 Jarvis role

Jarvis adds a **Study** workspace to its existing owner-facing shell. It calls Study OS APIs; it does not duplicate scheduling or run model CLIs.

Surfaces:

1. **Today:** one next action, confirmed blocks, due pressure, and “why this.”
2. **Learn:** teach/check/cold/correction loop, one challenge at a time.
3. **Courses:** source status, concept map, assessments, weak prerequisites.
4. **Office hours & research:** preparation drafts and learner-approved follow-ups.
5. **Evidence:** artifact timeline, verified claims, gaps, export.
6. **Requirements:** source-versioned snapshots with stale warnings; never a static checklist from memory.

Jarvis state words: `loading`, `ready`, `needs-source`, `needs-confirmation`, `stale`, `blocked`, `degraded`. Missing data renders “not verified,” not zero or complete.

### 11.3 Nova role

Nova stores durable narrative knowledge and relationships, not high-frequency telemetry. Write only meaningful events:

- course/interest decisions;
- office-hours or adviser interaction outcomes;
- research interests, readings, commitments, and feedback;
- evidence artifact summaries with original pointers/hashes;
- transfer goals and decisions;
- weekly learning synthesis when explicitly useful.

Do not write every answer, confidence value, latency, due date, or mastery update to Nova. Store a Study OS deep link and aggregate evidence instead.

Suggested page shapes:

```text
education/purdue/<term>/<course>
people/<canonical-person>
research/interests/<topic>
evidence/<artifact-id>
goals/stanford-transfer
```

Before discussing a known person, course decision, project, or transfer goal, Hermes queries Nova for existing context. Study OS remains functional when Nova is unavailable; outbox events retry and Jarvis shows degraded sync honestly.

### 11.4 Event contract

```json
{
  "event_id": "evt_01...",
  "event_type": "study.concept_stage_changed",
  "occurred_at": "...",
  "aggregate": {"type": "concept", "id": "42", "version": 8},
  "payload": {
    "from": "spaced",
    "to": "transfer",
    "reason_codes": ["delayed_success", "transfer_due"],
    "study_deep_link": "study://concept/42"
  },
  "privacy": "learner_only",
  "schema_version": "1.0"
}
```

Use an SQLite transactional outbox. Consumers deduplicate by `event_id`. Delivery failure never rolls back a committed learning attempt.

---

## 12. HTTP/API contracts

Version all new routes under `/api/v1`. Existing routes remain compatibility adapters.

```text
GET  /api/v1/today?minutes=20
POST /api/v1/sessions
GET  /api/v1/sessions/{id}/next
POST /api/v1/attempts/preview
POST /api/v1/attempts/commit
POST /api/v1/sources
GET  /api/v1/sources/{id}/status
POST /api/v1/ingestions
GET  /api/v1/jobs/{id}
GET  /api/v1/courses
GET  /api/v1/courses/{id}/readiness
GET  /api/v1/requirements?snapshot=active
POST /api/v1/calendar/proposals
POST /api/v1/calendar/blocks/{id}/confirm
POST /api/v1/office-hours/preparations
POST /api/v1/evidence
GET  /api/v1/evidence/export
GET  /api/v1/health
```

### Safe challenge payload

```json
{
  "attempt_id": "att_01...",
  "session_id": "ses_01...",
  "question_id": 17,
  "concept": {"id": 5, "name": "..."},
  "phase": "cold",
  "prompt": "...",
  "choices": [],
  "input_kind": "proof",
  "confidence_required": true,
  "source": {"title": "...", "source_version_id": 9},
  "reason_codes": ["prerequisite_blocker", "recent_lapse"]
}
```

It must not include answer, correct choice, explanation, rubric keys, source quote that reveals the answer, or scheduler internals sufficient to game grading.

### Attempt preview

Preview reveals correction evidence but does not mutate state when grading is ambiguous. Commit requires the same `attempt_id`, locked confidence, measured latency, and an allowed rating. A second identical commit returns the original receipt. A conflicting second payload returns HTTP 409.

---

## 13. Interfaces and interaction design

### Today

Above the fold:

- “Next: 20-minute mixed retrieval” or “Learn prerequisite X first.”
- Start button.
- Why selected: maximum three reason labels.
- Confirmed next study block and nearest verified assessment.

Below the fold: course readiness, correction debt, source freshness, and evidence capture prompts. Avoid a dashboard maze.

### Study chamber

- One task.
- Phase label (`Teach`, `Check`, `Cold`, `Transfer`).
- Source identity without answer leakage.
- Keyboard-first response.
- Confidence locked before submission.
- Latency recorded silently; never use a countdown unless explicitly practicing time pressure.
- Correction identifies the earliest error, expected reasoning, and exact source evidence.
- Learner rating for ambiguous work.
- Next due and mastery delta after commit.

### Accessibility

Semantic controls, 44px targets, visible focus, aria-live feedback, no color-only status, mobile at 375px without overflow, math rendered accessibly, reduced motion, and complete non-keyboard alternatives.

---

## 14. Safety, privacy, and academic integrity

### Academic-integrity modes

Every assessment/source has a policy mode:

- `learn`: explanations and worked examples allowed.
- `practice`: analogous problems and feedback allowed.
- `graded_restricted`: concepts, Socratic hints, error localization, and rubric checks only; no answer generation.
- `open_solution`: solution support allowed because the learner/instructor source explicitly permits it.
- `unknown`: default to `graded_restricted` until clarified.

The learner cannot bypass provenance by merely renaming a graded assignment “practice”; the UI preserves source type and asks for policy confirmation.

### External-action boundaries

Explicit confirmation is required for:

- sending email/messages;
- submitting coursework or applications;
- confirming calendar events beyond an approved routine policy;
- publishing/sharing artifacts;
- writing sensitive interaction summaries to Nova when consent is unclear.

Never type or store passwords, access tokens, student IDs, protected education records, or application credentials in prompts/logs. Keep secrets outside the repository. Encrypt remote backups; local-first is default.

### Model-data minimization

- Send only the relevant source window and bounded learner context.
- Redact grades, identifiers, and other people's private data unless necessary and approved.
- Do not send calendar event descriptions when free/busy is sufficient.
- Make model/provider and data-retention policy inspectable in settings.

---

## 15. Metrics and evaluation

### Primary learning metrics

- Delayed cold-retrieval success by concept and interval.
- Transfer success on novel, independently attempted problems.
- Calibration: Brier score or confidence-bin accuracy, especially overconfident misses.
- Correction effectiveness: probability of correct cold retry after a miss.
- Retention efficiency: durable successes per independent attempt/minute.
- Prerequisite unblock time.

### Operational metrics

- Time from opening Today to first attempt.
- Source ingestion acceptance rate (`accepted / returned`) and rejection reasons.
- Duplicate commit prevention.
- Scheduler replay determinism.
- Calendar proposal conflicts and confirmation rate.
- Stale requirement count.
- Nova outbox age/failure rate.

### Guardrails

- No increase in answer leakage.
- No mastery credit from reading/scaffolded checks alone.
- No calendar overlap or writes without authority.
- No unsupported requirement or evidence claim.
- No degradation in sleep/protected-time constraints when supplied.
- Engagement metrics never override delayed recall or transfer outcomes.

Weekly review compares cohorts within the same learner over time; it does not claim causal improvement from small samples. Show uncertainty and sample counts.

---

## 16. MVP phases

### Phase 0 — stabilize current engine (1–2 weeks)

- Add schema-migration ledger and idempotent `attempt_id`.
- Freeze current scheduler behavior in replay fixtures.
- Add health, version, and disposable E2E harness.
- Preserve existing database and UI.

**Exit:** old DB migrates without loss; duplicate review commits are impossible; complete existing lesson loop passes in a temporary DB.

### Phase 1 — Study OS learning core (2–3 weeks)

- Add tracks, courses, concepts, edges, `mastery_states`, sessions, and attempt events.
- Implement state machine and deterministic priority/composition engine.
- Backfill `(campaign, topic)` concepts and compare compatibility calculations.
- Add `/api/v1/today`, sessions, preview, and commit.

**Exit:** teach → checks → cold → correction → delayed review → transfer works end to end with no answer leakage and deterministic replay.

### Phase 2 — source/assessment ingestion + calendar proposals (2–3 weeks)

- Add immutable source versions, assessments, source locators, tracked generation jobs, and acceptance counts.
- Add syllabus/assignment confirmation UI.
- Add free/busy adapter and proposal-only planner.

**Exit:** a disposable syllabus fixture creates only quoted facts, an assessment plan, conflict-free proposed blocks, and grounded study content.

### Phase 3 — Jarvis/Hermes/Nova integration (2–3 weeks)

- Expose MCP/typed tools.
- Add Jarvis Study workspace.
- Add transactional outbox and Nova sync worker.
- Add office-hours preparation and post-interaction capture.

**Exit:** Jarvis shows the same authoritative next action as Study OS; Hermes cannot bypass commit validation; Nova outage does not block studying and later sync deduplicates.

### Phase 4 — transfer evidence track (2 weeks)

- Add requirements versioning, stale detection, evidence artifacts/claims, export.
- Seed official authority URLs without hard-coded claims.
- Add gap view and adviser-verification actions.

**Exit:** every exported requirement and claim resolves to a source version/artifact locator; no admission or credit prediction exists.

### Later, only after sufficient data

- Replace simple intervals with a validated FSRS-like model only after offline replay shows improvement.
- Code sandboxes and rubric-based proof review.
- Richer research reading trails.
- Multi-device sync with explicit conflict resolution and encryption.

---

## 17. Acceptance tests

### Migration and authority

1. **Given** a copy of the current DB, **when** migrations run twice, **then** all existing material/questions/reviews remain and the second run is a no-op.
2. **Given** a current review POST retried with the same `attempt_id`, **then** exactly one review/mastery/outbox event exists and both responses return one receipt.
3. **Given** the same `attempt_id` with conflicting payload, **then** HTTP 409 is returned and state is unchanged.
4. **Given** no official source import, **then** the Purdue/Stanford requirement lists contain no asserted requirements.
5. **Given** a changed official page hash, **then** a new source version is stored and dependent requirements become stale, not silently overwritten.

### Learning loop

6. A new concept with unmet knowledge opens Teach, not unsupported cold retrieval, unless the learner explicitly requests diagnostic mode.
7. Reading the lesson and completing scaffolded checks cannot mark the concept mastered/durable.
8. A missed check remains on that check and reveals only its correction.
9. A passed set of checks unlocks a concept-specific cold/transfer challenge, not the global due queue.
10. Challenge payloads never expose answer, correct choice, explanation, answer-bearing quote, or hidden rubric.
11. Recognition is graded by exact choice identity without an LLM.
12. Ambiguous typed/proof responses reveal the expected evidence and await learner rating without committing.
13. A cold miss with confidence 5 ranks ahead of an otherwise equal confidence-2 miss for remediation.
14. Latency/confidence modifiers cannot turn an incorrect answer into a passing mastery observation.
15. A derivable concept cannot reach durable without independent transfer and delayed success.
16. An arbitrary fact can reach durable via delayed retrieval without a contrived transfer problem.
17. Queue generation avoids adjacent same concepts when alternatives exist and is deterministic under a fixed seed/time/state.
18. Replaying attempt events with the same scheduler version reproduces every mastery state and due date.

### Grounding

19. A generated item with a quote absent from the source is rejected.
20. A problem-only source cannot produce a scored answer unless a solution source or verified deterministic solution is linked.
21. A request over schema `maxItems` is split into legal batches and records requested/returned/accepted/persisted separately.
22. Prompt-like instructions embedded in uploaded material are ignored and cannot trigger tools or writes.
23. Duplicate/near-duplicate questions are rejected without discarding valid siblings in the batch.

### Planning

24. Calendar proposals never overlap confirmed busy blocks or protected buffers.
25. Missing/stale assessment provenance removes assessment urgency from scheduler scoring and shows “needs verification.”
26. A missed study block replans remaining time without a penalty or fabricated completion.
27. Calendar writes remain proposed until confirmation unless a bounded policy explicitly covers the block.

### Relationships and evidence

28. Office-hours preparation includes learner attempts and source links but sends nothing automatically.
29. A completed interaction can store deterministic next actions in Study OS and a consented summary in Nova without duplicating attempt telemetry.
30. An evidence claim without artifact hash and locator cannot become verified or enter export.
31. Nova outage leaves core study/review commits available; retry later creates one Nova artifact/page per outbox event.
32. Export contains no admission probability, transfer-credit promise, or invented requirement.

### UI/E2E

33. In a disposable DB, a real browser completes Teach → checks → cold attempt → correction → successful retry → persisted next due.
34. Browser QA passes at desktop and 375px, keyboard-only, reduced-motion, visible focus, and screen-reader feedback.
35. The production learner DB is never used for synthetic reviews; test server health, port, title, URL, and fixture ID are asserted before interaction.
36. Jarvis Today and `GET /api/v1/today` agree on next action ID, reason codes, and source freshness.

---

## 18. First implementation tickets

1. `migration-001`: schema ledger, `attempt_id`, unique index, replay fixture.
2. `domain-001`: tracks/courses/concepts/backfill; parity report against current topic mastery.
3. `engine-001`: concept stage machine and versioned observation/scheduler functions.
4. `api-001`: `/api/v1/sessions`, safe next payload, preview, idempotent commit.
5. `test-001`: disposable full-loop E2E and answer-leak contract tests.
6. `source-001`: immutable source versions, locators, trust levels, generation-run counts.
7. `planning-001`: assessments and proposal-only conflict-free block planner.
8. `integration-001`: MCP tools + transactional outbox.
9. `jarvis-001`: Study workspace consuming typed API only.
10. `nova-001`: selective durable event consumer with deduplication and outage recovery.
11. `evidence-001`: artifact hash/locator verification and export.
12. `requirements-001`: official-source fetch/version/stale workflow with zero hard-coded claims.

---

## 19. Definition of done

A release is complete only with observed evidence for:

- forward migration on a copied current DB and a second no-op run;
- deterministic unit/property tests and scheduler replay;
- API answer non-disclosure and idempotent commits;
- grounding validator counts and rejection reasons;
- live health endpoints;
- a browser journey against isolated state;
- calendar conflict tests;
- Nova outage/recovery deduplication;
- source-resolvable evidence export;
- no unverified Purdue/Stanford requirements in persistent state.

A plan, successful syntax check, mocked health response, or generated fixture alone is not completion.
