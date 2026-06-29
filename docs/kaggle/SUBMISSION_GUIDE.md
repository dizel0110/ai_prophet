# Kaggle Submission Guide — AI Prophet (Massage Therapy AI)

**Deadline:** July 6, 2026, 23:59 PT  
**Track:** Concierge Agents (personal wellness assistant)  
**Branch:** `kaggle`  
**Demo:** https://dizel0110-kaggle-massage-agent.hf.space/demo  
**GitHub:** https://github.com/dizel0110/ai_prophet  
**Total Score Possible:** 100 pts (Pitch 30 + Implementation 70)

---

## 📋 Scoring Breakdown

### Category 1: The Pitch (30 pts)
| Criteria | Points | How to Max |
|----------|--------|------------|
| Core Concept & Value | 10 | Clear problem → agent solution → real impact |
| YouTube Video | 10 | 5-min video: problem → demo → architecture → build story |
| Writeup | 10 | 2500 words max, architecture, images, track fit |

### Category 2: The Implementation (70 pts)
| Criteria | Points | How to Max |
|----------|--------|------------|
| Technical Implementation | 50 | All 6 concepts demonstrated, clean code, tools, architecture |
| Documentation | 20 | README, setup instructions, diagrams, comments in code |

### Required Concepts (min 3 of 6)
We target **all 6** for max points:
| # | Concept | Where | Status | Plan |
|---|---------|-------|--------|------|
| 1 | Multi-agent (ADK) | Code | ✅ DONE | 6 agents, Workflow, FunctionTools |
| 2 | Deployability | Video | ✅ DONE | Docker, HF Space live |
| 3 | MCP Server | Code | 🔲 DAY 1 | Connect Playwright MCP to Technique Expert |
| 4 | Security features | Code | 🔲 DAY 2 | API key auth on /demo endpoints |
| 5 | Agent skills | Code | 🔲 DAY 2 | Wrap FunctionTools as ADK Skill classes |
| 6 | Antigravity | Video | 🔲 DAY 5 | Show Antigravity IDE in video |

---

## 🗓️ Timeline (8 days to July 6)

### DAY 1 — MCP Server (Jun 29, ~1h)
**Goal:** Wire Playwright MCP into Technique Expert agent

Steps:
1. Add `mcp` to `requirements.txt`
2. In `core/adk/tools.py`: create `PlaywrightMCPTool` — wraps `ProphetMCPClient.call_tool("browser_navigate", ...)` as an ADK `FunctionTool`
3. Attach it to `technique_expert_agent` alongside `web_search_tool`
4. The Technique Expert can now: search web + browse pages for technique details
5. Test: run demo → real AI mode → verify tool call works

**Video hook:** Show code in Antigravity: `tools.py` → MCP tool class → attach to agent.

---

### DAY 2 — Security + Agent Skills (Jun 30, ~2h)
**Goal:** API key protection + ADK Skills refactor

**Security (1h):**
1. Add `DEMO_API_KEY` env var to `.env.example`, `config.py`
2. In `main.py`: simple `@require_demo_key` decorator on `/api/demo/consult` and `/api/demo/upload`
3. Frontend: if key is in config, send as `X-API-Key` header; if not, show "⚠️ No API key — demo in mock-only mode"
4. Judges can set key themselves or just see the mechanism in code

**Agent Skills (1h):**
1. Create `core/adk/skills.py`:
   - `class WebSearchSkill(BaseTool)` or use ADK's `@agent_skill` pattern
   - `class MediaSearchSkill`
   - `class QuestionAnalyzerSkill`
2. Each skill wraps the existing function with metadata, description, version
3. Replace `FunctionTool` references in `agents.py` with `Skill` instances
4. Keep `FunctionTool` wrappers as fallback (progressive enhancement)

**Video hook:** Show code: `skills.py` → Skill class → attach to agent. Show `main.py` → `require_demo_key`.

---

### DAY 3 — Polish + Documentation (Jul 1, ~1.5h)
**Goal:** Clean code, ADK features table, README update

1. Add architecture diagram to `README.md` (Mermaid → inline or ASCII):
   ```mermaid
   graph LR
     User -->|complaint| QA[Questionnaire Agent]
     QA --> PD[Photo Diagnostician]
     PD --> VM[Video/Motion Agent]
     VM --> TE[Technique Expert]
     TE --> MC[Music Curator]
     MC --> FE[Final Expert]
     FE -->|report| User
   ```
2. Create `docs/kaggle/SCORING_CHECKLIST.md` — what judge will check per criteria
3. Add inline comments to key files (`workflow.py`, `agents.py`, `tools.py`) explaining design decisions
4. Clean up dead code (remove legacy `core/agents/orchestrator.py` references if unused)

---

### DAY 4 — Kaggle Writeup (Jul 2, ~2h)
**Goal:** Submit writeup on Kaggle (2500 words max)

Open: https://www.kaggle.com/competitions/vibecoding-agents-capstone-project/projects
→ **New Writeup**

**Structure (max 2500 words):**
1. **Title:** "AI Prophet — Multi-Agent Massage Therapy Consultant"
2. **Subtitle:** "6 ADK 2.0 agents with MCP, security, and skills pipeline"
3. **Track:** Concierge Agents
4. **Cover Image:** Screenshot of demo page showing 6 agents + consultation report

**Content sections:**
- Problem: Massage therapists lack AI tools for client analysis
- Solution: 6-agent ADK 2.0 pipeline (questionnaire → vision → motion → techniques → music → report)
- Architecture: Workflow graph, agent definitions, tool system
- Key Concepts Demonstrated:
  1. Multi-agent ADK system with Workflow orchestration
  2. MCP Server (Playwright) for web browsing
  3. Security features (API key auth on endpoints)
  4. Agent skills (reusable Skill classes)
  5. Deployability (Docker, HF Spaces, auto-restart)
  6. Antigravity IDE for vibe coding
- Technical Highlights: HF Router fallback, photo validation, progressive UI
- Impact: Democratizes massage therapy assessment

**Attachments:**
- Media Gallery: cover image + architecture diagram
- Project Link: https://github.com/dizel0110/ai_prophet
- Video: YouTube URL

---

### DAY 5 — Record Video (Jul 3, ~3h)
**Goal:** 5-min YouTube video showing all 6 concepts

**Script (5 min):**

| Time | Segment | What to Show |
|------|---------|-------------|
| 0:00-0:30 | Problem | "Massage therapists have no AI tools..." + text overlay |
| 0:30-1:30 | Demo | HF Space → fill complaint → Start Consultation → 6 agents light up → report |
| 1:30-2:30 | Code (Antigravity) | Open Antigravity → show `workflow.py` (6 agents pipeline) → `agents.py` (agent definitions) |
| 2:30-3:00 | MCP Server | Show `tools.py` → PlaywrightMCPTool → Technique Expert uses it |
| 3:00-3:30 | Security | Show `@require_demo_key` in `main.py` → X-API-Key header |
| 3:30-4:00 | Agent Skills | Show `skills.py` → Skill class → attached to agents |
| 4:00-4:30 | Deployability | Show `Dockerfile`, HF Space live |
| 4:30-5:00 | Wrap | GitHub link, architecture diagram, thank you |

**Recording tools:**
- OBS Studio (free) or built-in screen recorder
- Antigravity IDE: install from https://ide.antigravity.dev/
- Record at 1920x1080
- Upload to YouTube as Unlisted (share link with judges)

---

### DAY 6 — Review + Submit (Jul 4, ~1h)
**Goal:** Final checks and submission

**Checklist before submit:**
- [ ] GitHub repo public (Settings → Danger Zone → Change visibility)
- [ ] No API keys in code (grep for `AIza`, `sk-`, `hf_`)
- [ ] `.env.example` has `DEMO_API_KEY=` placeholder
- [ ] Demo works at https://dizel0110-kaggle-massage-agent.hf.space/demo
- [ ] Mock mode works without API keys
- [ ] Real AI mode works with user's key
- [ ] MCP tool call works (Technique Expert can browse)
- [ ] Writeup under 2500 words
- [ ] Video on YouTube (Unlisted, link in writeup)
- [ ] Cover image attached
- [ ] GitHub URL attached
- [ ] Track selected: Concierge Agents

**Submit:**
1. Open https://www.kaggle.com/competitions/vibecoding-agents-capstone-project/projects
2. Your writeup → "Submit" button (top right)
3. Confirm submission
4. Done ✅

---

### BUFFER (Jul 5-6)
Use for:
- Fix anything that broke
- Re-record video if needed
- Answer judge comments
- Final sanity check

---

## 📌 Track Justification: Concierge Agents

> "The opportunity for personal AI agents to streamline and simplify people's lives is incredible. From managing the invite list for a party to planning a garden, or helping manage complicated medications — safe and secure agents can free time for things that really matter."

**Our fit:** Massage therapy consultation is a personal wellness service. The AI agent acts as a **concierge** that:
- Guides the client through complaint intake
- Analyzes photos for visual diagnosis
- Recommends tailored massage techniques
- Curates music for the session
- Produces a comprehensive report

This is not a business automation tool (Business track) — it's a personal assistant for health and wellness.

---

## 📊 ADK Features Matrix (for writeup)

| # | ADK Feature | Where | Status |
|---|-------------|-------|--------|
| 1 | Multi-Agent Orchestration | `core/adk/workflow.py` | ✅ 6 agents with edges |
| 2 | Tool Use | `core/adk/tools.py` | ✅ 3 FunctionTools |
| 3 | Sessions | `core/adk/session.py` | ✅ InMemorySessionService |
| 4 | Observability | `workflow.py` logging | ✅ Per-agent logging |
| 5 | Deployment | Dockerfile, HF Space | ✅ Live at *.hf.space |
| 6 | Agent Evaluation | `tests/test_adk_workflow.py` | ✅ 216 tests |
| 7 | Human-in-the-Loop | Demo mock/AI toggle | ✅ |
| 8 | MCP Protocol | `core/adk/tools.py` | ✅ Playwright MCP |
| 9 | Security | `main.py` `@require_demo_key` | ✅ API key auth |
| 10 | Agent Skills | `core/adk/skills.py` | ✅ ADK Skill classes |

---

## 🚨 Critical Reminders

1. **NO API KEYS IN CODE.** All keys via env vars or user input.
2. **Video is mandatory** — without it, -10 pts and possible disqualification.
3. **Submit before July 6 23:59 PT** — not June 30 (that was the course badge deadline).
4. **Draft = not submitted** — click "Submit" button, not just "Save".
5. **Make repo public** — judges can't evaluate private repos.
6. **Antigravity in video** — they specifically want to see Antigravity IDE.
7. **Live demo optional** — HF Space is a bonus; GitHub code is required anyway.
