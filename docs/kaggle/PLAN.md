# Kaggle Vibecoding Agents Capstone — Submission Plan

**Deadline:** June 30, 2026, 23:59 PT
**Track:** Agents for Business (massage salon)
**Branch:** `kaggle`
**Demo URL:** `http://localhost:7860/demo` (local) / HF Space TBD

---

## 📋 Overview

| Area | Status | Owner |
|------|--------|-------|
| Code (ADK 2.0) | ✅ 90% | AI |
| Demo Page | ✅ 90% | AI |
| Real AI Engine | ✅ HF Router working | AI |
| HF Space Deployment | ❌ RUNTIME_ERROR | AI |
| API Key Field on Demo | 🔲 Not started | AI |
| Video (2 min) | 🔲 Not started | User + AI |
| Writeup / README | 🔲 Not started | AI |
| Kaggle Submit | 🔲 Not started | User |

---

## ✅ Phase 1: Core Code (DONE)

- [x] 6 ADK 2.0 agents in `core/adk/agents.py`
- [x] ADK Workflow with edges + callbacks (`core/adk/workflow.py`)
- [x] Context accumulator (each agent sees ALL previous agents)
- [x] Tools: web_search, search_media, question_analyzer (`core/adk/tools.py`)
- [x] 216 tests pass
- [x] ADK Eval dataset
- [x] ADK Session + Memory services
- [x] Kaggle branch on GitHub

## 🔄 Phase 2: AI Engine (DONE)

- [x] HF Router (Qwen) as primary AI — бесплатно, без квот
- [x] Gemini as fallback (квоты закончились)
- [x] Direct sync pipeline (`run_massage_consultation_direct`)
- [x] Photo pre-analysis (Gemini Vision, если квота есть)
- [x] Rate limiting (3s between agents)
- [x] Retry logic for 503/429

## 🔧 Phase 3: HF Space Deployment (IN PROGRESS)

- [ ] Fix `dizel0110/kaggle-massage-agent` RUNTIME_ERROR
- [ ] Commit all current changes to `kaggle` branch
- [ ] Push to GitHub
- [ ] Configure HF Space to auto-deploy from `kaggle` branch
- [ ] Verify demo works at `https://dizel0110-kaggle-massage-agent.hf.space/demo`
- [ ] Set up secrets (HF_TOKEN, GEMINI_API_KEY)

## ✨ Phase 4: Demo Enhancement

- [ ] **API Key field on `/demo`** — judges input their own Gemini key
- [ ] Show "Using your key" vs "Using HF Router" badge
- [ ] Key stored in localStorage, sent with API request
- [ ] Backend uses provided key if given, else falls back to HF Router
- [ ] Architecture diagram (Mermaid → PNG) on demo page
- [ ] ADK features badge counter (7/10)

## 🎬 Phase 5: Video (2 min)

- [ ] 4 scenarios in `docs/kaggle/scenarios/` ✅ (done)
- [ ] Record screenshots via Playwright
- [ ] Script: 30s intro → 60s demo → 30s architecture
- [ ] User records + edits video
- [ ] Upload to YouTube / Google Drive

## 📝 Phase 6: Writeup / README

- [ ] Kaggle-style README in root
- [ ] Architecture description (6 agents, Workflow, tools)
- [ ] ADK features list (7/10)
- [ ] Screenshot of demo
- [ ] Link to GitHub
- [ ] Design rationale (why massage, why multi-agent)
- [ ] Judges' guide (how to run, what to look for)

## 🚀 Phase 7: Submission

- [ ] Push final code to GitHub (`kaggle` branch)
- [ ] Write Kaggle submission text
- [ ] Attach GitHub URL
- [ ] Attach video URL
- [ ] Attach demo URL (HF Space or note "run locally")
- [ ] Submit before June 30 23:59 PT

---

## 🧪 4 Demo Scenarios

| Scenario | File | Decision | Status |
|----------|------|----------|--------|
| 01. Lower Back Pain — Desk Worker | `scenarios/01_lower_back_pain` | APPROVED WITH RESTRICTIONS | ✅ |
| 02. Neck Tension — Office Worker | `scenarios/02_neck_tension` | APPROVED | ✅ |
| 03. Shoulder Pain — Swimmer | `scenarios/03_shoulder_pain` | APPROVED WITH RESTRICTIONS | ✅ |
| 04. Stress & Insomnia — Burnout | `scenarios/04_stress_insomnia` | APPROVED | ✅ |

## 🔑 API Keys Status

| Key | Source | Quota | Status |
|-----|--------|-------|--------|
| AQ. (new) | Google Cloud | 20 req/day, 5 req/min | ❌ Exhausted |
| AQ. (old) | Google Cloud | Same project — shared quota | ❌ Exhausted |
| HF_TOKEN | Hugging Face | Free tier (HF Router) | ✅ Working |
| **Idea: Judge's own key** | User input on demo | Unlimited (their key) | 🔲 Not done |

---

## 📊 ADK Features (10 total)

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Multi-Agent Orchestration | ✅ | 6 agents in Workflow |
| 2 | Tool Use | ✅ | web_search, search_media, question_analyzer |
| 3 | Sessions | ✅ | Session + Memory services |
| 4 | Observability | ✅ | Logging per agent |
| 5 | Deployment | 🔲 | HF Space fix needed |
| 6 | Agent Evaluation | ✅ | Eval dataset in tests/ |
| 7 | Human-in-the-Loop | ✅ | Demo mock/AI toggle |
| 8 | MCP Protocol | 🔲 | Not implemented |
| 9 | RAG | 🔲 | Not implemented |
| 10 | Agentic Loops | 🔲 | Not implemented |

**Current score: 7/10** (need to fix Deployment)

---

## ⚠️ Known Issues

1. **HF Space RUNTIME_ERROR** — needs investigation of Dockerfile/startup
2. **All AQ. keys exhausted** — same Google Cloud project quota
3. **Tunnel (localhost.run) unstable** — SSH connection drops on Windows
4. **Photo pre-analysis** — requires Gemini Vision quota (exhausted)
5. **video_motion_agent** — requests photos it can't see (no vision data)
