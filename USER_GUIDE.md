# AI Prophet — User Guide

## 🧑‍⚕️ AI Massage Consultation

The bot has a multi-agent system: 5 AI specialists analyze your condition and give a recommendation.

### How to run

```
/massage → "AI-консультация"
```

### Step 1: Questionnaire (12 questions)

The bot asks you one by one:

| # | Question | How to answer |
|---|----------|---------------|
| 1 | Your name | Type text |
| 2 | Age | Type number |
| 3 | Gender | Tap button |
| 4 | Complaints/pain | Describe (text) |
| 5-7 | Pain location, type, duration | Tap buttons |
| 8 | Chronic diseases | Check or skip |
| 9 | Contraindications | Type or /skip |
| 10 | Medications | Type or /skip |
| 11 | Lifestyle | Describe (text) |
| 12 | Extra info | Type or /skip |

You can also fill everything in the Mini App (tap "Открыть салон" → AI tab → "Заполнить анкету").

### Step 2: Upload photos/video

After the questionnaire, you can upload:

- **📸 Photos of your back** (2-3 angles) — the Visual Diagnostician will analyze posture, detect scoliosis, kyphosis, asymmetry
- **🎥 Video** (walk, bends, 5-10 sec) — the Movement Specialist will analyze gait and range of motion

Just send them as regular photos/videos. The bot saves them.

### Step 3: Run analysis

Tap **"🧑‍⚕️ Запустить анализ"**. The 5 AI agents work sequentially:

```
Анкетолог → (Фото → Виз.Диагност) → (Видео → Движения) → Техники → Финальный Эксперт
```

The final result contains:

```
1. STATUS: Admitted / Limited / Not admitted
2. REASON: brief justification
3. RECOMMENDED TECHNIQUES: list with reasoning
4. AREAS OF ATTENTION: which body parts need work
5. CONTRAINDICATED: what to avoid
6. SUGGESTED SESSIONS: number
7. EXTRA RECOMMENDATIONS
```

### Cancel anytime

Send `/stop` to cancel the consultation.

---

## 🎵 Massage Music Database

The bot has **curated YouTube links** for 8 massage genres:

| Genre | Buttons |
|-------|---------|
| Ambient, Classical, Nature, Jazz | Genre buttons |
| Spa, Thai, Acoustic, Binaural | Genre buttons |

These are **external links** (not pre-downloaded). Clicking opens the YouTube video.

Additionally, the bot automatically searches Jamendo/SoundCloud/YouTube via `search_media_content()` and can download MP3 files for you as a playlist.

---

## 🤖 VIP Mode

`/dizel0110` — unlocks Gemini (better quality) + all features.

Default password: `prophet2026` (change via `VIP_PASSWORD` env).

---

## 🎛 Download Limits

`/limits` — control max duration and filesize for audio downloads.

---

## 📝 Settings

`/settings` — choose AI engine: Auto (HF→Gemini), Gemini only, or HF only.

---

## 🧑‍⚕️ Dynamic Specialists

You can create **custom AI specialists** on the fly — personal consultants for any topic.

### Commands

| Command | What it does |
|---------|-------------|
| `/specialist <role>` | Create a specialist (e.g., `/specialist expert in sports massage`) |
| `/specialists` | List your specialists |
| `/dismiss <name>` | Remove a specialist |
| `/exit_specialist` | Exit specialist chat |

### How it works

1. Type `/specialist эксперт по стоун-терапии` (or any role)
2. The bot generates a name + system prompt for this specialist
3. You can immediately chat with the specialist — ask questions, get advice
4. The specialist guides you toward the massage salon services
5. To exit specialist chat, send `/exit_specialist`

### Auto-detection by AI

The main AI can also decide **on its own** to create a specialist when it senses you need deep expertise in a specific area. The specialist will appear automatically and start a conversation.

### From the Massage Salon menu

In `/massage`, tap "🧑‍⚕️ Создать специалиста" to manage your specialists directly from the massage menu.

---

## For developers

See `AGENTS.md` for architecture, `core/agents/registry.py` to add/modify agents.
