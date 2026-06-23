# AI Prophet — Kaggle Vibecoding Agents Capstone

## Architecture Deep-Dive

AI Prophet is a **6-agent massage consultation system** built on Google ADK 2.0. It replaces the traditional 15-minute manual intake with an automated AI pipeline that produces a diagnostic report, technique recommendations, and a personalized music playlist.

### Why 6 agents?

| # | Agent | Group | Why separate? |
|---|-------|-------|---------------|
| 1 | **Questionnaire Analyst** | Intake | Validates client data, flags contraindications before any analysis |
| 2 | **Photo Diagnostician** | Vision | Vision-only (Gemini Flash), separate prompt for posture & asymmetry |
| 3 | **Video Motion Specialist** | Vision | Motion analysis — different prompt, frame extraction pipeline |
| 4 | **Technique Expert** | Synthesis | Combines all upstream data, recommends modalities & pressure zones |
| 5 | **Music Curator** | Synthesis | Therapy-matched playlist (genre, duration, rationale) |
| 6 | **Head Expert** | Report | Final synthesis agent — produces structured report from all outputs |

Each agent has a **separate system prompt** (`core/adk/agents.py`), a distinct `CallbackContext` in the pipeline, and receives only the data it needs.

### Pipeline Design

```
Input (complaint + age + gender) 
  → Questionnaire Analyst (contraindication check)
  → Photo Diagnostician ∥ Video Motion Specialist (parallel vision)
  → Technique Expert (combines all data)
  → Music Curator (genre + duration + track count)
  → Head Expert (final structured report)
```

The pipeline is implemented as a **sequential ADK `Workflow`** with function-call nodes (`core/adk/workflow.py`). Each node:
1. Receives context from previous nodes via `ctx.session.state`
2. Calls the Gemini model via `generate_content()` with its specific agent prompt
3. Stores result in session state
4. Passes accumulated context to the next node

### How the Demo Works

The `/demo` page at `main.py:173-744` is a self-contained HTML+JS application served by FastAPI. It:

1. **Shows a form** — complaint text, age, gender, optional photo upload
2. **Uses progressive simulation** — agent rows light up one-by-one (every ~2.8s) to show the pipeline in action, even before the real AI response arrives
3. **Fetches real data** — POST to `/api/demo/consult` which runs the full ADK workflow
4. **Populates real responses** — each agent row expands with the actual AI output, maintaining the visual timeline

### AI Engine Fallback Chain

```
User-provided Gemini API key → Gemini 2.5 Flash (primary)
  ↓ on 503/rate-limit
  HF Router (Qwen 2.5-7B-Instruct)
    ↓ on error
  Mock data (guaranteed response, no API call)
```

### Photo Validation

Uploaded photos are validated via `/api/demo/validate-photo`:
1. **Gemini Vision** examines the photo and returns `{valid, body_part, message}`
2. **Cross-validation** compares detected `body_part` against the complaint text keywords
3. **Warning shown** if a mismatch is found (e.g., "Photo shows 'shoulders' but complaint mentions 'back'")
4. When Gemini is unavailable, validation is skipped gracefully

For the demo, photos are saved to `temp/` and cleaned on restart. Three example posture photos are available in `data/test_photos/`.

## ADK 2.0 Features Used

| Feature | Implementation | Location |
|---------|---------------|----------|
| **Multi-Agent Orchestration** | 6 agents in sequential Workflow with `add_callback` nodes | `core/adk/workflow.py` |
| **Tool Use** | `web_search`, `search_media_content` tools for music + technique lookup | `core/adk/tools.py` |
| **Session Management** | `InMemorySessionService` for stateless per-request state | `core/adk/session.py` |
| **Memory Service** | `InMemoryMemoryService` for conversation context | `core/adk/session.py` |
| **Callback Context** | Each agent node receives typed context from prior nodes | `core/adk/workflow.py` |
| **Async Runner** | `AsyncRunner.run_async()` with per-agent callback streaming | `core/adk/workflow.py` |
| **Event Logging** | Agent start/end events with timestamps and content | `core/adk/workflow.py` |
| **Fallback Model** | HF Router (Qwen 7B) when Gemini quota is exhausted | `core/adk/workflow.py:_call_ai()` |

### Not Yet Used

| Feature | Why | Priority |
|---------|-----|----------|
| **Callable Agent** (ADK Agent class) | Workflow uses function nodes — simpler for sequential pipeline | Low — sequential pipeline doesn't need agent autonomy |
| **Evaluation** | `massage_consultation_eval` dataset created but ADK eval not integrated | Medium — judges don't run eval |
| **RAG** | External knowledge base for massage techniques | Low — Gemini already knows massage protocols |
| **Human-in-the-Loop** | Approval callback exists but disabled in demo | Low — judges want autonomous pipeline |

## How Judges Can Test

### Quick Test (No API Key)
1. Open the demo: `/demo`
2. Leave "Use AI" unchecked → click **Start Consultation**
3. All 6 agents execute progressively with mock data
4. Click any agent row to expand and see per-agent output
5. After completion, the structured report appears below

### Real AI Test (With Your Gemini API Key)
1. Get a free API key at [aistudio.google.com](https://aistudio.google.com/apikey)
2. Check **"Use AI (real agents)"** → paste your key → click **Verify**
3. Click **Start Consultation**
4. Agents light up progressively (~3s each), then populate with real AI content
5. Each agent's response is expandable — click any row
6. The full report shows the synthesized diagnosis

### Photo Upload Test
1. Upload a back/shoulder photo via drag & drop or click
2. Photo is validated: shows ✅ + detected body part
3. Try uploading a mismatch (e.g., shoulder photo with back complaint) → ⚠️ warning
4. The Visual Diagnostician agent uses the photo for postural analysis

### Engine Fallback
- Without a Gemini key → HF Router (Qwen 7B) → slightly slower but works
- With a key that's exhausted → falls back gracefully to HF Router

## File Structure

```
core/adk/             # ADK 2.0 module
├── __init__.py        # Exports
├── agents.py          # 6 agent instructions + system prompts
├── workflow.py        # Pipeline: nodes, orchestration, fallback
├── tools.py           # FunctionTool wrappers for web/media search
└── session.py         # InMemory services

main.py                # FastAPI server + /demo page + all API endpoints
  lines 173-744        # KAGGLE_DEMO_HTML — complete frontend
  lines 746-856        # /demo, /api/demo/* endpoints

docs/kaggle/           # Kaggle-specific documentation
├── PLANS.md           # Development plan & progress
├── scenarios/         # 4 pre-defined test scenarios with mock agent outputs
└── README.md          # This file
```

## Key Technical Decisions

1. **All-in-one HTML frontend** — No build step, no framework, no npm. The entire demo page (HTML+CSS+JS) is a Python triple-quoted string in `main.py`. This makes deployment trivial on HF Spaces.

2. **User-provided API key** — Judges bring their own Gemini key. No shared server key quota. Key is stored in `localStorage` (client-side) and sent per-request.

3. **Progressive UI simulation** — Even in real AI mode, agents light up progressively so the user sees pipeline flow. When the backend response arrives (~25s), real content replaces placeholder states.

4. **HF Router as fallback** — `router.huggingface.co` provides OpenAI-compatible endpoints for free. When Gemini is overloaded (common on free tier), Qwen 2.5-7B handles all 6 agent calls reliably.

5. **Photo cross-validation** — Validates not just that the photo shows anatomy, but that the body part matches the described complaint. Warns but doesn't block — judges decide.

6. **Single-file agents** — All 6 agent prompts in `agents.py`. Easy to inspect and modify without framework overhead.

## June 30 Deadline Checklist

- [x] 6 ADK agents with distinct prompts
- [x] Sequential pipeline with data passing between agents
- [x] Web demo page with progressive agent visualization
- [x] Photo upload + AI validation + cross-check with complaint
- [x] Gemini API key field + verify + fallback to HF Router
- [x] Expandable per-agent content (click to see individual output)
- [x] Structured final report
- [x] Stop/Cancel button
- [x] English-language UI
- [ ] HF Space deployment (dizel0110/kaggle-massage-agent)
- [ ] 2-min demo video
- [ ] Root README final pass
- [ ] Competition submission (GitHub URL + video + writeup)

---

*Built with Google ADK 2.0 for the Kaggle Vibecoding Agents Capstone. June 2026.*
