import asyncio
import logging
import os
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
)
from core.adk.session import get_session_service, get_memory_service, create_session
from core.adk.tools import question_analyzer_tool

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


def _pre_analyze_photos(photo_paths: list[str]) -> str:
    """Send photos to Gemini Vision for pre-analysis. Returns text summary injected into workflow."""
    if not photo_paths:
        return ""
    api_key = os.getenv("GEMINI_API_KEY")
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
        except Exception as e:
            logger.warning(f"Photo pre-analysis failed for {path}: {e}")
            results.append(f"--- Photo: {Path(path).name} ---\n[Analysis error: {e}]")
    return "\n\n" + "\n\n".join(results) + "\n\n"


def _pre_analyze_video(video_frames_paths: list[str]) -> str:
    """Send video frames to Gemini Vision for movement analysis."""
    if not video_frames_paths:
        return ""
    api_key = os.getenv("GEMINI_API_KEY")
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


def _analyze_and_pass(node_input: str) -> Event:
    """Validate questionnaire completeness and pass to the next agent."""
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


def _accumulate_context(node_input: str) -> Event:
    """Format accumulated context for the next specialist."""
    return Event(
        output=f"[CONTEXT] The following is the full consultation data so far.\n\n{node_input}"
    )


def _extract_music_recommendation(node_input: str) -> Event:
    """Parse music recommendation from technique expert output."""
    return Event(
        output=f"[MUSIC_REQ] Based on the assessment above, recommend appropriate music.\n\n{node_input}"
    )


def _finalize_report(node_input: str) -> Event:
    """Format the final consultation report."""
    return Event(
        message=f"📋 **Massage Consultation Complete**\n\n{node_input}\n\n"
        f"_Generated by AI Prophet ADK Workflow_"
    )


_analyze_node = _analyze_and_pass
_accumulate_node = _accumulate_context
_music_extract_node = _extract_music_recommendation
_finalize_node = _finalize_report


massage_workflow = Workflow(
    name="massage_consultation_workflow",
    edges=[
        ("START", questionnaire_agent, _analyze_node, photo_diagnost_agent),
        (photo_diagnost_agent, video_motion_agent),
        (video_motion_agent, _accumulate_node, technique_expert_agent),
        (technique_expert_agent, _music_extract_node, music_recommend_agent),
        (music_recommend_agent, _finalize_node, final_synthesis_agent),
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


async def run_massage_consultation(
    chat_id: int,
    user_message: str,
    photo_paths: Optional[list[str]] = None,
    video_frames_paths: Optional[list[str]] = None,
) -> list[dict]:
    """Run a full massage consultation workflow with optional vision support.

    Photos and video frames are pre-analyzed by Gemini Vision before the
    workflow runs, with results injected as text context for all agents.

    Args:
        chat_id: User/chat identifier
        user_message: Initial user message describing the complaint
        photo_paths: Optional list of photo file paths for visual analysis
        video_frames_paths: Optional list of video frame file paths

    Returns:
        List of event dicts from the workflow execution
    """
    session_id = f"{chat_id}_massage_consultation"

    session = _session_service.create_session_sync(
        app_name="ai_prophet",
        user_id=str(chat_id),
        session_id=session_id,
    )

    # Pre-analyze media and inject results as text context
    photo_analysis = _pre_analyze_photos(photo_paths or [])
    video_analysis = _pre_analyze_video(video_frames_paths or [])
    if photo_analysis or video_analysis:
        user_message += (
            "\n\n========== MEDIA ANALYSIS ==========\n"
            f"{photo_analysis}{video_analysis}"
            "====================================="
        )

    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=user_message)],
    )

    events = []
    for event in _runner.run(
        user_id=str(chat_id),
        session_id=session_id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            text = "".join(
                p.text for p in event.content.parts if hasattr(p, "text") and p.text
            )
            if text:
                author = getattr(event, "author", "system")
                events.append({
                    "author": author,
                    "content": text,
                    "invocation_id": event.invocation_id,
                })
                logger.info(f"[{author}] {text[:120]}...")

    return events
