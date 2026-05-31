import logging
import os
import base64
import mimetypes
from typing import Optional, List
from google import genai
from google.genai import types as genai_types
import requests

from config import GEMINI_KEY, HF_TOKEN, HF_TASKS, HF_SYSTEM_PROMPT, FALLBACK_MODELS, IS_HF_SPACE

logger = logging.getLogger(__name__)


class AgentResult:
    def __init__(self, agent_id: str, agent_name: str, content: str, error: Optional[str] = None):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.content = content
        self.error = error

    def to_dict(self) -> dict:
        return {"agent_id": self.agent_id, "agent_name": self.agent_name, "content": self.content, "error": self.error}

    def is_success(self) -> bool:
        return self.error is None and bool(self.content)


class AgentBase:
    """
    Базовый класс ИИ-агента.
    Стратегия (бесплатно для всех):
      1. HF Router (free, мультимодальный: Qwen7B / Llama Vision / Whisper)
      2. Gemini (если HF не ответил)
    """
    def __init__(self, agent_id: str, name: str, role_prompt: str, model_type: str = "text"):
        self.agent_id = agent_id
        self.name = name
        self.role_prompt = role_prompt
        self.model_type = model_type  # "text" | "vision" | "audio"
        self.hf_token = HF_TOKEN.strip() if HF_TOKEN else None
        self.gemini_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

    def _system_prompt(self) -> str:
        return (
            f"Ты — {self.name} в системе AI Prophet.\n\n"
            f"Твоя роль: {self.role_prompt}\n\n"
            f"Отвечай строго по своей роли. Будь конкретным и профессиональным. "
            f"Твои ответы будут использованы финальным экспертом.\n"
            f"ВАЖНО: Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы."
        )

    # ────────────── HF (бесплатно, основной канал) ──────────────

    def _hf_text(self, prompt: str) -> Optional[str]:
        if not self.hf_token:
            return None
        try:
            resp = requests.post(
                "https://router.huggingface.co/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.hf_token}", "Content-Type": "application/json"},
                json={
                    "model": HF_TASKS.get("text", "Qwen/Qwen2.5-7B-Instruct"),
                    "messages": [{"role": "user", "content": f"{HF_SYSTEM_PROMPT}\n\nЗапрос для {self.name}.\n\n{prompt}"}],
                    "max_tokens": 4096,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            logger.warning(f"HF text {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"HF text error: {e}")
        return None

    def _hf_vision(self, text: str, image_path: str) -> Optional[str]:
        if not self.hf_token:
            return None
        try:
            with open(image_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            resp = requests.post(
                "https://router.huggingface.co/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.hf_token}", "Content-Type": "application/json"},
                json={
                    "model": HF_TASKS.get("vision", "meta-llama/Llama-3.2-11B-Vision-Instruct"),
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": f"{self._system_prompt()}\n\n{text}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
                    ]}],
                    "max_tokens": 4096,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            logger.warning(f"HF vision {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"HF vision error: {e}")
        return None

    # ────────────── Gemini (бекап) ──────────────

    def _gemini_text(self, prompt: str) -> Optional[str]:
        if not self.gemini_client:
            return None
        for model in FALLBACK_MODELS[:2]:
            try:
                resp = self.gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(temperature=0.3, max_output_tokens=4096),
                )
                if resp and resp.text:
                    return resp.text.strip()
            except Exception as e:
                logger.warning(f"Gemini {model}: {e}")
        return None

    def _gemini_vision(self, text: str, image_path: str) -> Optional[str]:
        if not self.gemini_client:
            return None
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        try:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            for model in FALLBACK_MODELS[:2]:
                try:
                    resp = self.gemini_client.models.generate_content(
                        model=model,
                        contents=[f"{self._system_prompt()}\n\n{text}",
                                  genai_types.Part.from_bytes(data=img_bytes, mime_type=mime)],
                        config=genai_types.GenerateContentConfig(temperature=0.3, max_output_tokens=4096),
                    )
                    if resp and resp.text:
                        return resp.text.strip()
                except Exception as e:
                    logger.warning(f"Gemini vision {model}: {e}")
        except Exception as e:
            logger.warning(f"Gemini vision error: {e}")
        return None

    # ────────────── Публичные методы ──────────────

    def process_text(self, text: str) -> AgentResult:
        """Обработка текста: HF → Gemini"""
        prompt = f"{self._system_prompt()}\n\n---\n\n{text}"

        result = self._hf_text(prompt)
        if result:
            return AgentResult(self.agent_id, self.name, result.strip())

        result = self._gemini_text(prompt)
        if result:
            return AgentResult(self.agent_id, self.name, result.strip())

        return AgentResult(self.agent_id, self.name, "", error="HF + Gemini failed")

    def process_vision(self, text: str, image_path: str) -> AgentResult:
        """Обработка изображения: HF Vision → Gemini Vision"""
        result = self._hf_vision(text, image_path)
        if result:
            return AgentResult(self.agent_id, self.name, result.strip())

        result = self._gemini_vision(text, image_path)
        if result:
            return AgentResult(self.agent_id, self.name, result.strip())

        return AgentResult(self.agent_id, self.name, "", error="HF + Gemini vision failed")

    def process_video_frames(self, text: str, video_path: str, frame_count: int = None) -> AgentResult:
        """Извлекает кадры из видео и анализирует их через vision"""
        if frame_count is None:
            frame_count = 2 if IS_HF_SPACE else 3  # на HF меньше кадров — экономим ресурсы

        frames = _extract_frames(video_path, frame_count)
        if not frames:
            return self.process_text(f"{text}\n\n[Видео не удалось обработать, анализирую по описанию]")

        results = []
        for i, frame_path in enumerate(frames):
            r = self.process_vision(f"{text} (кадр {i+1}/{len(frames)})", frame_path)
            if r.is_success():
                results.append(r.content)
            _safe_delete(frame_path)

        if not results:
            return AgentResult(self.agent_id, self.name, "", error="Video frame analysis failed")

        return AgentResult(self.agent_id, self.name, "\n\n".join(results))


def _extract_frames(video_path: str, count: int = 3) -> List[str]:
    """Извлекает N кадров из видео через ffmpeg"""
    import subprocess
    import uuid
    from config import TEMP_DIR

    if not os.path.exists(video_path):
        logger.warning(f"Video not found: {video_path}")
        return []

    duration = _get_video_duration(video_path)
    if duration <= 0:
        duration = 10

    frames = []
    for i in range(count):
        ts = duration * (i + 1) / (count + 1)
        out = os.path.join(TEMP_DIR, f"frame_{uuid.uuid4().hex[:8]}_{i}.jpg")
        try:
            subprocess.run(
                ["ffmpeg", "-i", video_path, "-ss", str(ts), "-vframes", "1", "-q:v", "2", out, "-y"],
                capture_output=True, timeout=15,
            )
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                frames.append(out)
        except Exception as e:
            logger.warning(f"Frame extraction error: {e}")
    return frames


def _safe_delete(path: str):
    """Безопасное удаление файла."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _get_video_duration(video_path: str) -> float:
    """Получает длительность видео через ffprobe"""
    import subprocess
    import re
    try:
        result = subprocess.run(
            ["ffprobe", "-i", video_path, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=%s"],
            capture_output=True, text=True, timeout=10,
        )
        match = re.search(r"(\d+\.?\d*)", result.stdout)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return 0
