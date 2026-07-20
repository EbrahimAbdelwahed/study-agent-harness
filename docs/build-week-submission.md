# OpenAI Build Week submission package

Status: prepared, not submitted  
Release: Study Agent Harness 0.2.0 alpha  
Category: Education

## Devpost copy

### Title

Study Agent Harness

### Tagline

The durable, source-grounded execution layer for AI tutors students can trust.

### Long description

Medical school did not give me one study workflow. It gave me many disconnected
ones: source-file management, deterministic chunking, study-material and
question generation, past-exam simulation, source fact-checking, and correction.
Study Agent Harness turns the reliability lessons from that lived workflow into
an open-source core for durable AI tutors.

The project is not another chat application. A model may propose what to do, but
it does not own the learner state, course authority, source truth, or execution.
The harness keeps canonical state in an append-only event stream, snapshots
trusted sources, projects inspectable learner evidence, runs versioned skills
through playbooks, and can replay the same state deterministically. Provider
adapters remain technical boundaries, so the tutor core is model neutral.

The Build Week demo starts where a student is: “I have ten minutes. Help me
understand heart valves.” It uses a sanitized anatomy fixture and the real
bounded host runner to complete a grounded action, suspend for clarification,
refresh evidence, and resume. The visible trace is
`completed → suspended → completed`; the same trace is replayed through scripted
and recorded-provider decision adapters without making a network request.

This foundation can let future tutor products adapt conversationally without
turning the conversation into the source of truth. The immediate impact is
trust: a learner or developer can inspect which source snapshot, evidence
sequence, capability, and transition produced an outcome.

### Built with

- Python 3.12/3.13 and the Python standard library
- SQLite for local operational persistence and projections
- Versioned skills and playbooks
- Provider-neutral model and tutor-decision ports
- Optional OpenAI Responses adapter (`openai` extra); not required by the demo
- Pytest, Ruff, mypy, and GitHub Actions
- GPT-5.6 through Codex as the primary Build Week implementation environment

### How Codex and GPT-5.6 were used

GPT-5.6 through Codex was the primary implementation environment during Build
Week. Codex supported a spec-driven workflow: specification, clarification,
beads, bounded implementation, offline tests, and review. An adapted agent
flywheel maintained small tasks, explicit success/stop criteria, and durable
technical memory.

This describes the Build Week workflow and does not claim that every historical
line of the project was generated during Build Week.

### Challenges

The central challenge was keeping an adaptive tutor flexible without letting a
model become the owner of authority, truth, or durable state. The implementation
therefore separates model decisions from trusted execution, makes suspension and
resumption explicit, and tests failure paths offline.

### Accomplishments

- Event-sourced canonical study state and deterministic replay
- Source snapshots and inspectable evidence state
- Provider-neutral skills, playbooks, capabilities, and adapter boundaries
- A bounded tutor host with clarification, recovery, and fail-closed behavior
- A clean-wheel, one-command offline anatomy demo

### What we learned

Agentic tutoring benefits from a flexible conversation, but reliability comes
from moving authority and truth outside the model. Small executable specs,
deterministic fixtures, and explicit stop criteria made that boundary testable.

### What's next

After Build Week, the next work is to let third-party tutor products embed the
harness, validate the public contracts with more hosts, and improve contributor
ergonomics without weakening replay or provider neutrality.

### Repository and supported platform

- Repository: https://github.com/EbrahimAbdelwahed/study-agent-harness
- License: Apache-2.0
- Platform: Python 3.12 or 3.13; CI on Ubuntu, Build Week verification on macOS arm64

### Judge/testing instructions

```bash
git clone https://github.com/EbrahimAbdelwahed/study-agent-harness.git
cd study-agent-harness
python3.12 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/study-agent-demo "I have ten minutes. Help me understand heart valves."
```

Expected terminal evidence:

- the bundled `heart-valves.md` source snapshot and checksum;
- two source evidence lines;
- `completed → suspended → completed`;
- evidence sequence `1 → 2`;
- scripted/recorded parity `true`;
- an explicit statement that no network, credential, SDK, or provider call ran.

For the complete quality gate:

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src
```

### Required-field answers

- Category: Education
- Public repository: https://github.com/EbrahimAbdelwahed/study-agent-harness
- Demo video: pending public YouTube URL
- Codex Session ID (`/feedback`): pending; paste the session ID before submission
- Submission status: prepared locally; no Devpost fields have been submitted

## Final voiceover and burned-in caption transcript

This timed master is both the final English voiceover script and the caption
transcript. Target duration: 2:45 at a calm 130 words per minute.

### 0:00–0:18

Medical school did not give me one study workflow. It gave me dozens of
disconnected ones. Notes lived in one place, questions in another, and every new
AI conversation forgot what had happened before. The problem was not access to
another chatbot. It was reliability.

### 0:18–0:38

Study Agent Harness is an open-source, provider-neutral execution layer for
durable AI tutors. It keeps the tutor flexible enough to meet a student where
they are, while making source grounding, learner state, and execution
inspectable and replayable.

### 0:38–1:30

Here is the real offline anatomy demo. The learner starts freely: “I have ten
minutes. Help me understand heart valves.” The harness captures a sanitized
Markdown source as a trusted snapshot, exposes its checksum, and selects only
the evidence needed for this trace.

The tutor completes an initial grounded action, then suspends: “Which valve
should we focus on?” The learner chooses the aortic valve. Before resuming, the
harness refreshes learner evidence from sequence one to sequence two. It then
resumes the exact continuation instead of inventing a new conversation.

The result is visible: completed, suspended, completed. The scripted adapter and
the recorded provider adapter replay the same runner and gateway trace. This
demo needs no network, credentials, model SDK, or provider call.

### 1:30–1:58

The trust boundary is deliberate. The model does not own learner state,
authority, or truth. Canonical state is an append-only event stream. Source
snapshots and evidence are inspectable. Skills describe capabilities, playbooks
compose behavior, and adapters translate technical provider protocols. Replay
can reconstruct what the tutor knew and which transition it executed.

### 1:58–2:25

GPT-5.6 through Codex was the primary implementation environment during Build
Week. Codex supported a spec-driven workflow: specification, clarification,
beads, bounded implementation, offline tests, and review. An adapted agent
flywheel maintained small tasks, explicit success and stop criteria, and durable
technical memory. That workflow helped keep the architecture provider neutral
and each change independently verifiable.

### 2:25–2:45

This is version 0.2.0 alpha: an open-source core, ready for tutor products to
embed and extend. Not another study chat. A durable execution layer for tutors
that students can trust. Clone the public repository and run the entire anatomy
trace with one command.

## Timestamped shot list

| Time | Picture | Asset | On-screen text |
|---|---|---|---|
| 0:00–0:08 | Fragmented notes, terminal panes, and study cards moving apart | Generated abstract B-roll | `Disconnected workflows` |
| 0:08–0:18 | Real repository tree and README | Real screen recording | `The missing layer: reliability` |
| 0:18–0:30 | Simple verified architecture diagram | Diagram | `Model proposes · Harness executes` |
| 0:30–0:38 | Real `pyproject.toml`, skills, playbooks, adapters | Real screen recording | `Open source · Provider neutral · Event sourced` |
| 0:38–0:48 | Install and invoke `study-agent-demo` | Real screen recording | Learner prompt highlighted |
| 0:48–1:02 | Source fixture, checksum, and evidence lines | Real screen recording | `Trusted source snapshot` |
| 1:02–1:17 | Trace pauses at clarification | Real screen recording | `suspended` |
| 1:17–1:30 | Evidence `1 → 2`, resumption, parity | Real screen recording | `completed → suspended → completed` |
| 1:30–1:44 | Animated event stream flowing into projections | Generated abstract B-roll + diagram | `State is outside the model` |
| 1:44–1:58 | Real event, skill, playbook, and adapter files | Real screen recording | `Replayable · Inspectable · Replaceable` |
| 1:58–2:12 | Real specs and bead files, then focused commit history | Real screen recording | `spec → clarification → bead → implementation` |
| 2:12–2:25 | Real tests, Ruff, mypy, and clean-wheel demo | Real screen recording | `offline test → review` |
| 2:25–2:37 | Restrained anatomy texture resolves into project title | Generated abstract B-roll | `Study Agent Harness 0.2.0 alpha` |
| 2:37–2:45 | Real GitHub repository and demo command | Real screen recording | `github.com/EbrahimAbdelwahed/study-agent-harness` |

Composition target: approximately 60% real screen recording, 25% typography,
diagrams, and motion, and 15% abstract B-roll.

## Recording plan

Record at 1920×1080, 30 fps, with a 16:9 crop, large terminal text, hidden
notifications, and no credentials or private paths visible. Capture these real
clips in order:

1. Public GitHub repository landing page and README.
2. Repository tree: event state, skills, playbooks, adapters, and demo fixture.
3. Clean environment install, then the full `study-agent-demo` command and output.
4. A slower second pass over source checksum/evidence, suspension, refresh, and replay.
5. Spec/bead documents and a concise `git log` view.
6. Full verification summary: tests, Ruff, mypy, wheel build, installed smoke.

Use only real output from the verified project. Zoom or crop existing pixels;
never recreate terminal text or product screens in motion graphics.

## Thumbnail concept

A graphite-black field with a thin warm-white event stream crossing a restrained
anatomical line texture. Large title: `AI tutors need memory they can prove.`
Small lower label: `Study Agent Harness`. No faces, avatars, product mockups, or
third-party branding.

## HeyGen production brief

- Format: 1920×1080, 16:9, 2:40–2:50, public YouTube-safe export.
- Presenter: none. No avatar, digital twin, talking head, face, or face clone.
- Audio: calm English voiceover, neutral international accent, approximately
  130 words per minute; no imitation voice.
- Captions: burned-in English captions from the timed master; warm white, large,
  high contrast, at most two lines.
- Palette: black, warm white, graphite, with subtle muted anatomical red/blue
  accents. No Apple marks, terminology, music, or imitated assets.
- Real footage: the six clips in the recording plan.
- Generated footage: four short abstract clips only—fragmented study materials,
  event stream, anatomy-inspired editorial texture, and title transition.
- Diagrams: only the verified model → runner → gateway → event/state boundary
  and skill/playbook/provider relationships.
- Music: restrained licensed ambient bed, mixed well below narration, or none.
- Prohibited: fake UI, terminal output, code, metrics, user studies,
  integrations, medical claims, or capabilities.
- Planned paid renders: one final assembly after one local timing/caption review;
  no paid render is authorized yet.

The exact remaining/required credit line must be filled from the authenticated
official HeyGen Remote MCP before any render proposal is approved.
