import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional

from google.adk import Workflow, Event
from google.adk.runners import Runner
from google.genai import types as genai_types

from core.adk.agents import (
    questionnaire_agent,
    photo_diagnost_agent,
    video_motion_agent,
    technique_expert_agent,
    music_recommend_agent,
    final_synthesis_agent,
    QUESTIONNAIRE_INSTRUCTION,
    PHOTO_DIAGNOST_INSTRUCTION,
    VIDEO_MOTION_INSTRUCTION,
    TECHNIQUE_EXPERT_INSTRUCTION,
    MUSIC_RECOMMEND_INSTRUCTION,
    FINAL_SYNTHESIS_INSTRUCTION,
)
from core.adk.session import get_session_service, get_memory_service, create_session
from core.adk.tools import question_analyzer_tool
from config import HF_TOKEN

# Alias for workflow direct pipeline
QUESTIONNAIRE_AGENT_INSTRUCTION = QUESTIONNAIRE_INSTRUCTION

logger = logging.getLogger(__name__)

VISION_PROMPT = """Analyze this photo for postural assessment and visible musculoskeletal signs.
Describe what you see in terms of:
1. Posture and spinal alignment
2. Visible asymmetries (shoulders, scapulae, pelvis, hips)
3. Muscle tension patterns or atrophy
4. Any visible deformities or abnormalities
5. Overall body balance

Focus ONLY on observable physical signs. Do NOT diagnose medical conditions.
Be specific and precise — mention left/right differences clearly."""

MOVEMENT_PROMPT = """Analyze this video frame for movement and biomechanical assessment.
Describe what you observe in terms of:
1. Joint positioning and range of motion indicators
2. Symmetry of movement patterns
3. Compensatory patterns
4. Areas of restriction
5. Balance and weight distribution

Focus ONLY on observable movement patterns. Do NOT diagnose medical conditions.
Be specific about which body parts show asymmetry or restriction."""


def _pre_analyze_photos(photo_paths: list[str], gemini_key: str = "") -> str:
    """Send photos to Gemini Vision for pre-analysis. Returns text summary injected into workflow."""
    if not photo_paths:
        return ""
    api_key = gemini_key or os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("No GEMINI_API_KEY for photo pre-analysis")
        return "\n[PHOTO PRE-ANALYSIS: Skipped — no API key]\n"

    from google import genai
    client = genai.Client(api_key=api_key)
    results = []
    for path in photo_paths:
        try:
            with open(path, "rb") as f:
                data = f.read()
            ext = Path(path).suffix.lower()
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext.lstrip("."), "image/jpeg")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[VISION_PROMPT, genai_types.Part.from_bytes(data=data, mime_type=mime)],
            )
            results.append(f"--- Photo: {Path(path).name} ---\n{response.text}")
            time.sleep(3)
        except Exception as e:
            logger.warning(f"Photo pre-analysis failed for {path}: {e}")
            results.append(f"--- Photo: {Path(path).name} ---\n[Analysis error: {e}]")
    return "\n\n" + "\n\n".join(results) + "\n\n"


def _pre_analyze_video(video_frames_paths: list[str], gemini_key: str = "") -> str:
    """Send video frames to Gemini Vision for movement analysis."""
    if not video_frames_paths:
        return ""
    api_key = gemini_key or os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("No GEMINI_API_KEY for video pre-analysis")
        return "\n[VIDEO PRE-ANALYSIS: Skipped — no API key]\n"

    from google import genai
    client = genai.Client(api_key=api_key)
    results = []
    for path in video_frames_paths:
        try:
            with open(path, "rb") as f:
                data = f.read()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[MOVEMENT_PROMPT, genai_types.Part.from_bytes(data=data, mime_type="image/jpeg")],
            )
            results.append(f"--- Frame: {Path(path).name} ---\n{response.text}")
        except Exception as e:
            logger.warning(f"Video frame analysis failed for {path}: {e}")
            results.append(f"--- Frame: {Path(path).name} ---\n[Analysis error: {e}]")
    return "\n\n" + "\n\n".join(results) + "\n\n"


_context_accumulator: dict = {"full": ""}


def _reset_accumulator(initial_text: str) -> None:
    """Reset the context accumulator for a new workflow run."""
    _context_accumulator["full"] = initial_text


def _accumulate_for_video(node_input: str) -> Event:
    """Accumulate after photo diagnost for video motion agent."""
    full = _context_accumulator["full"] + f"\n\n=== Photo Diagnostician ===\n{node_input}"
    _context_accumulator["full"] = full
    time.sleep(3)
    return Event(output=full)


def _accumulate_for_technique(node_input: str) -> Event:
    """Accumulate after video motion for technique expert."""
    full = _context_accumulator["full"] + f"\n\n=== Movement Specialist ===\n{node_input}"
    _context_accumulator["full"] = full
    time.sleep(3)
    return Event(output=full)


def _accumulate_for_music(node_input: str) -> Event:
    """Accumulate after technique expert for music curator."""
    full = _context_accumulator["full"] + f"\n\n=== Technique Expert ===\n{node_input}"
    _context_accumulator["full"] = full
    time.sleep(3)
    return Event(
        output=f"[MUSIC_REQ] Full assessment data.\n\n{full}"
    )


def _accumulate_for_final(node_input: str) -> Event:
    """Accumulate after music curator for final synthesis."""
    full = _context_accumulator["full"] + f"\n\n=== Music Curator ===\n{node_input}"
    _context_accumulator["full"] = full
    time.sleep(3)
    return Event(message=f"📋 **Massage Consultation Complete**\n\n{full}\n\n"
                f"_Generated by AI Prophet ADK Workflow_")


def _analyze_and_pass(node_input: str) -> Event:
    """Validate questionnaire completeness, store in accumulator."""
    _context_accumulator["full"] = node_input
    import re
    checks = {
        "возраст|лет|age": "age",
        "жалоб|complaint|боль|pain": "complaints",
        "лока|locat|где|where": "location",
        "тип|type|характер|nature": "pain_type",
        "длитель|duration|как долго": "duration",
        "хронич|chronic|заболев": "chronic",
        "противопоказан|contraind": "contraindications",
    }
    found = []
    for pattern, field in checks.items():
        if re.search(pattern, node_input, re.IGNORECASE):
            found.append(field)
    info = f"[META] Questionnaire fields detected: {', '.join(found) or 'none'}"
    return Event(output=f"{info}\n\n{node_input}")


massage_workflow = Workflow(
    name="massage_consultation_workflow",
    edges=[
        ("START", questionnaire_agent, _analyze_and_pass, photo_diagnost_agent),
        (photo_diagnost_agent, _accumulate_for_video, video_motion_agent),
        (video_motion_agent, _accumulate_for_technique, technique_expert_agent),
        (technique_expert_agent, _accumulate_for_music, music_recommend_agent),
        (music_recommend_agent, _accumulate_for_final, final_synthesis_agent),
    ],
)


_session_service = get_session_service()
_memory_service = get_memory_service()

_runner = Runner(
    app_name="ai_prophet",
    agent=massage_workflow,
    session_service=_session_service,
    memory_service=_memory_service,
    auto_create_session=True,
)


def create_massage_workflow() -> Workflow:
    """Get the massage consultation workflow instance."""
    return massage_workflow


def _call_ai(prompt: str, system_instruction: str,
             gemini_key: str = "", hf_token_override: str = "") -> str:
    """Call AI with optional user-provided keys. Priority:
    1. User's Gemini key (if provided)
    2. HF Router (free, no quota)
    3. Server's Gemini key (if available)
    """
    user_gemini_key = gemini_key.strip()
    user_hf_token = hf_token_override.strip()

    # Try user's Gemini key first (fresh quota)
    if user_gemini_key:
        from google import genai
        try:
            client = genai.Client(api_key=user_gemini_key)
            gen = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            return gen.text
        except Exception as e:
            logger.warning(f"User Gemini key failed: {str(e)[:100]}")

    # Try HF Router (free, no quota)
    import requests
    hf_token = user_hf_token or (HF_TOKEN.strip() if HF_TOKEN else "")
    if hf_token:
        api_url = "https://router.huggingface.co/v1/chat/completions"
        headers = {"Authorization": f"Bearer {hf_token}", "Content-Type": "application/json"}
        payload = {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 4096,
        }
        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            logger.warning(f"HF Router error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"HF Router exception: {e}")
    else:
        logger.warning("HF_TOKEN not set, skipping HF Router")

    # Fallback: server's Gemini key
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        from google import genai
        client = genai.Client(api_key=api_key)
        try:
            gen = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            return gen.text
        except Exception as e:
            logger.warning(f"Server Gemini failed: {str(e)[:100]}")

    raise RuntimeError("All AI engines failed")


async def run_massage_consultation_direct(
    chat_id: int,
    user_message: str,
    photo_paths: Optional[list[str]] = None,
    video_frames_paths: Optional[list[str]] = None,
    gemini_key: str = "",
    hf_token: str = "",
) -> list[dict]:
    """Run a full massage consultation using direct sync Gemini calls.

    Bypasses ADK Runner (async API returns 503 currently) while keeping
    the same 6-agent pipeline and context accumulation.

    Args:
        chat_id: User/chat identifier
        user_message: Initial user message describing the complaint
        photo_paths: Optional list of photo file paths for visual analysis
        video_frames_paths: Optional list of video frame file paths
        gemini_key: User-provided Gemini API key (fresh quota)
        hf_token: User-provided HF token

    Returns:
        List of event dicts from the workflow execution
    """
    import time

    _reset_accumulator(user_message)

    # Pre-analyze media and inject results as text context
    photo_analysis = _pre_analyze_photos(photo_paths or [], gemini_key)
    video_analysis = _pre_analyze_video(video_frames_paths or [], gemini_key)
    extra = ""
    if photo_analysis or video_analysis:
        extra = (
            "\n\n========== MEDIA ANALYSIS ==========\n"
            f"{photo_analysis}{video_analysis}"
            "=====================================\n\n"
        )

    agents_config = [
        ("questionnaire_agent", QUESTIONNAIRE_AGENT_INSTRUCTION,
         f"{extra}Client data:\n{user_message}"),
        ("photo_diagnost_agent", PHOTO_DIAGNOST_INSTRUCTION,
         None),  # will use accumulator
        ("video_motion_agent", VIDEO_MOTION_INSTRUCTION, None),
        ("technique_expert_agent", TECHNIQUE_EXPERT_INSTRUCTION, None),
        ("music_recommend_agent", MUSIC_RECOMMEND_INSTRUCTION, None),
        ("final_synthesis_agent", FINAL_SYNTHESIS_INSTRUCTION, None),
    ]

    events = []

    for i, (name, instruction, prompt_override) in enumerate(agents_config):
        if prompt_override is not None:
            prompt = prompt_override
        else:
            full = _context_accumulator["full"]
            prompt = f"Previous assessment data:\n\n{full}"

        logger.info(f"[{name}] Calling AI...")
        try:
            text = await asyncio.to_thread(
                _call_ai, prompt, instruction,
                gemini_key=gemini_key, hf_token_override=hf_token,
            )
        except Exception as e:
            logger.error(f"[{name}] Failed: {e}")
            text = f"[{name} error: {e}]"

        events.append({"author": name, "content": text})
        logger.info(f"[{name}] Response: {text[:120]}...")

        # Accumulate context
        if i == 0:
            _context_accumulator["full"] = f"=== {name} ===\n{text}"
        else:
            _context_accumulator["full"] += f"\n\n=== {name} ===\n{text}"

        time.sleep(3)  # rate limit between agents

    return events
