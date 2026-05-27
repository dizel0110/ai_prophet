import json
import os
import time
import logging
from dataclasses import dataclass, asdict
from typing import Optional, List
from google import genai
from google.genai import types as genai_types
import requests

from config import GEMINI_KEY, HF_TOKEN, HF_TASKS, FALLBACK_MODELS
from core.agents.agent_base import AgentResult

logger = logging.getLogger(__name__)

SPECIALISTS_FILE = os.path.join("temp", "specialists.json")


@dataclass
class DynamicSpecialist:
    name: str
    role_description: str
    system_prompt: str
    created_at: float
    chat_id: int
    message_count: int = 0

    def to_dict(self) -> dict:
        return {**asdict(self), "__type__": "DynamicSpecialist"}

    @classmethod
    def from_dict(cls, d: dict) -> "DynamicSpecialist":
        d.pop("__type__", None)
        return cls(**d)


class SpecialistFactory:
    _gemini_client = None
    _hf_token = None

    @classmethod
    def _ensure_clients(cls):
        if cls._gemini_client is None:
            cls._gemini_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
        if cls._hf_token is None:
            cls._hf_token = HF_TOKEN.strip() if HF_TOKEN else None

    @classmethod
    def create(cls, chat_id: int, role_description: str, name: Optional[str] = None) -> Optional[DynamicSpecialist]:
        cls._ensure_clients()
        prompt = (
            f"Ты — создатель специалистов массажного салона AI Prophet.\n"
            f"Клиент хочет создать консультанта с описанием: \"{role_description}\"\n\n"
            f"Придумай КРАТКОЕ имя (2-4 слова) и системный промпт для этого специалиста.\n"
            f"Системный промпт должен включать:\n"
            f"- Роль и экспертизу\n"
            f"- Какие вопросы задавать клиенту\n"
            f"- Как направлять клиента к услугам массажного салона\n"
            f"- Запрет на медицинские диагнозы и назначение лекарств\n\n"
            f"Ответь строго JSON: {{\"name\": \"...\", \"system_prompt\": \"...\"}}"
        )

        text = ""
        if cls._gemini_client:
            for model in FALLBACK_MODELS[:2]:
                try:
                    resp = cls._gemini_client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=genai_types.GenerateContentConfig(temperature=0.3, max_output_tokens=1024),
                    )
                    if resp and resp.text:
                        text = resp.text.strip()
                        break
                except Exception as e:
                    logger.warning(f"Gemini create specialist {model}: {e}")

        if not text and cls._hf_token:
            try:
                resp = requests.post(
                    "https://router.huggingface.co/v1/chat/completions",
                    headers={"Authorization": f"Bearer {cls._hf_token}", "Content-Type": "application/json"},
                    json={
                        "model": HF_TASKS.get("text", "Qwen/Qwen2.5-7B-Instruct"),
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1024,
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"HF create specialist: {e}")

        if not text:
            return None

        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]
            data = json.loads(text)
            specialist = DynamicSpecialist(
                name=data.get("name", name or role_description[:30]),
                role_description=role_description,
                system_prompt=data.get("system_prompt", ""),
                created_at=time.time(),
                chat_id=chat_id,
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse specialist response: {e}")
            specialist = DynamicSpecialist(
                name=name or role_description[:30],
                role_description=role_description,
                system_prompt=role_description,
                created_at=time.time(),
                chat_id=chat_id,
            )

        _save_specialist(specialist)
        return specialist

    @classmethod
    def chat(cls, chat_id: int, specialist: DynamicSpecialist, user_message: str) -> AgentResult:
        cls._ensure_clients()
        prompt = (
            f"Ты — {specialist.name}.\n\n"
            f"{specialist.system_prompt}\n\n"
            f"Клиент: {user_message}\n\n"
            f"{specialist.name}:"
        )

        if cls._hf_token:
            try:
                resp = requests.post(
                    "https://router.huggingface.co/v1/chat/completions",
                    headers={"Authorization": f"Bearer {cls._hf_token}", "Content-Type": "application/json"},
                    json={
                        "model": HF_TASKS.get("text", "Qwen/Qwen2.5-7B-Instruct"),
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1024,
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    specialist.message_count += 1
                    _save_specialist(specialist)
                    return AgentResult(f"s_{chat_id}", specialist.name, content)
            except Exception as e:
                logger.warning(f"HF specialist chat: {e}")

        if cls._gemini_client:
            for model in FALLBACK_MODELS[:2]:
                try:
                    resp = cls._gemini_client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=genai_types.GenerateContentConfig(temperature=0.3, max_output_tokens=1024),
                    )
                    if resp and resp.text:
                        specialist.message_count += 1
                        _save_specialist(specialist)
                        return AgentResult(f"s_{chat_id}", specialist.name, resp.text.strip())
                except Exception as e:
                    logger.warning(f"Gemini specialist chat {model}: {e}")

        return AgentResult(f"s_{chat_id}", specialist.name, "", error="All AI engines failed")


def _save_specialist(specialist: DynamicSpecialist):
    os.makedirs("temp", exist_ok=True)
    data = _load_all_specialists()
    key = str(specialist.chat_id)
    if key not in data:
        data[key] = []
    lst = data[key]
    for i, s in enumerate(lst):
        if s.get("name", "").lower() == specialist.name.lower():
            lst[i] = specialist.to_dict()
            break
    else:
        lst.append(specialist.to_dict())
    _write_specialists(data)


def _load_all_specialists() -> dict:
    if not os.path.exists(SPECIALISTS_FILE):
        return {}
    try:
        with open(SPECIALISTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return {}


def _write_specialists(data: dict):
    try:
        with open(SPECIALISTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save specialists: {e}")


def get_specialists(chat_id: int) -> List[DynamicSpecialist]:
    data = _load_all_specialists()
    return [DynamicSpecialist.from_dict(s) for s in data.get(str(chat_id), [])]


def get_specialist(chat_id: int, name: str) -> Optional[DynamicSpecialist]:
    for s in get_specialists(chat_id):
        if s.name.lower() == name.lower():
            return s
    return None


def remove_specialist(chat_id: int, name: str) -> bool:
    data = _load_all_specialists()
    key = str(chat_id)
    if key not in data:
        return False
    lst = data[key]
    for i, s in enumerate(lst):
        if s.get("name", "").lower() == name.lower():
            lst.pop(i)
            _write_specialists(data)
            return True
    return False
