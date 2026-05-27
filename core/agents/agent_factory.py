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
    skills: str = ""

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
    def _call_llm(cls, prompt: str, system: str = "") -> Optional[str]:
        cls._ensure_clients()
        if cls._gemini_client:
            for model in FALLBACK_MODELS[:2]:
                try:
                    contents = f"{system}\n\n{prompt}" if system else prompt
                    resp = cls._gemini_client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=genai_types.GenerateContentConfig(temperature=0.3, max_output_tokens=1536),
                    )
                    if resp and resp.text:
                        return resp.text.strip()
                except Exception as e:
                    logger.warning(f"Gemini {model}: {e}")
        if cls._hf_token:
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": prompt})
            try:
                resp = requests.post(
                    "https://router.huggingface.co/v1/chat/completions",
                    headers={"Authorization": f"Bearer {cls._hf_token}", "Content-Type": "application/json"},
                    json={"model": HF_TASKS.get("text", "Qwen/Qwen2.5-7B-Instruct"), "messages": msgs, "max_tokens": 1536},
                    timeout=60,
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"HF: {e}")
        return None

    @classmethod
    def create(cls, chat_id: int, role_description: str, name: Optional[str] = None) -> Optional[DynamicSpecialist]:
        system = "Ты — создатель экспертов. Отвечай только в формате JSON."
        prompt_parts = ["Создай персонального консультанта."]
        if name:
            prompt_parts.append(f"Имя специалиста: \"{name}\"")
        if role_description:
            prompt_parts.append(f"Описание роли: \"{role_description}\"")
        prompt_parts.append('Верни JSON с полями:\n'
            '  name — короткое имя специалиста (2-4 слова, рус.)\n'
            '  role — его профессиональная роль (1 предложение)\n'
            '  skills — ключевые навыки (3-5 пунктов через запятую)\n'
            '  system_prompt — подробная инструкция для ИИ (на рус., 5-10 предложений):\n'
            '    • кто он, его опыт и экспертиза\n'
            '    • какие вопросы задавать клиенту для сбора информации\n'
            '    • как направлять клиента в массажный салон AI Prophet\n'
            '    • что НЕЛЬЗЯ делать (ставить диагнозы, назначать лекарства)\n'
            '    • стиль общения (профессиональный, заботливый, понятный)\n\n'
            'Пример: {"name": "Мастер стоун-терапии", "role": "Специалист по массажу горячими камнями", "skills": "стоун-терапия, терморегуляция, расслабление мышц, работа с энергетическими центрами", "system_prompt": "Ты — Мастер стоун-терапии с 8-летним опытом. Узнай у клиента: есть ли проблемы с давлением, кожей, варикозом. Рекомендуй стоун-терапию при мышечном напряжении, стрессе. Не назначай медицинских процедур. Общайся спокойно и уверенно."}\n\n'
            'Ответь JSON: {"name": "...", "role": "...", "skills": "...", "system_prompt": "..."}')
        prompt = "\n\n".join(prompt_parts)

        text = cls._call_llm(prompt, system)

        if not text:
            return None

        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]
            data = json.loads(text)
            sp = data.get("system_prompt", "")
            specialist = DynamicSpecialist(
                name=data.get("name", name or role_description[:30]),
                role_description=data.get("role", role_description),
                system_prompt=sp if sp else f"Ты — {data.get('name', role_description[:30])}. {data.get('role', role_description)}. Навыки: {data.get('skills', '')}. Консультируй клиента по своей специализации, задавай уточняющие вопросы, направляй в массажный салон AI Prophet. Не ставь медицинских диагнозов. Общайся профессионально и заботливо.",
                skills=data.get("skills", ""),
                created_at=time.time(),
                chat_id=chat_id,
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse specialist response: {e}")
            fallback_name = name or role_description[:30] or "Специалист"
            fallback_role = role_description or (name or "консультант")
            specialist = DynamicSpecialist(
                name=fallback_name,
                role_description=fallback_role,
                system_prompt=f"Ты — {fallback_name}. Твоя роль: {fallback_role}. Консультируй клиента, задавай вопросы, направляй в массажный салон. Не ставь диагнозов.",
                skills="",
                created_at=time.time(),
                chat_id=chat_id,
            )

        _save_specialist(specialist)
        return specialist

    @classmethod
    def chat(cls, chat_id: int, specialist: DynamicSpecialist, user_message: str) -> AgentResult:
        cls._ensure_clients()
        history = _load_conversation(chat_id, specialist.name)

        # Gemini first — лучше следует system prompt
        if cls._gemini_client:
            for model in FALLBACK_MODELS[:2]:
                try:
                    ctx = specialist.system_prompt + "\n\n"
                    for h in history[-4:]:
                        ctx += f"{h['role']}: {h['content']}\n"
                    ctx += f"user: {user_message}\n\n{specialist.name}:"
                    resp = cls._gemini_client.models.generate_content(
                        model=model,
                        contents=ctx,
                        config=genai_types.GenerateContentConfig(temperature=0.3, max_output_tokens=1024),
                    )
                    if resp and resp.text:
                        specialist.message_count += 1
                        _save_specialist(specialist)
                        _save_conversation(chat_id, specialist.name, user_message, resp.text.strip())
                        return AgentResult(f"s_{chat_id}", specialist.name, resp.text.strip())
                except Exception as e:
                    logger.warning(f"Gemini specialist chat {model}: {e}")

        # HF fallback — обычно Qwen
        if cls._hf_token:
            try:
                msgs = [{"role": "system", "content": specialist.system_prompt}]
                for h in history:
                    msgs.append(h)
                msgs.append({"role": "user", "content": user_message})
                resp = requests.post(
                    "https://router.huggingface.co/v1/chat/completions",
                    headers={"Authorization": f"Bearer {cls._hf_token}", "Content-Type": "application/json"},
                    json={
                        "model": HF_TASKS.get("text", "Qwen/Qwen2.5-7B-Instruct"),
                        "messages": msgs,
                        "max_tokens": 1024,
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    specialist.message_count += 1
                    _save_specialist(specialist)
                    _save_conversation(chat_id, specialist.name, user_message, content)
                    return AgentResult(f"s_{chat_id}", specialist.name, content)
            except Exception as e:
                logger.warning(f"HF specialist chat: {e}")

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


CONVERSATIONS_FILE = os.path.join("temp", "specialist_convs.json")

def _load_conversation(chat_id: int, specialist_name: str) -> list:
    if not os.path.exists(CONVERSATIONS_FILE):
        return []
    try:
        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        key = f"{chat_id}_{specialist_name}"
        return data.get(key, [])
    except Exception:
        return []

def _save_conversation(chat_id: int, specialist_name: str, user_msg: str, bot_msg: str):
    os.makedirs("temp", exist_ok=True)
    data = {}
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    key = f"{chat_id}_{specialist_name}"
    if key not in data:
        data[key] = []
    data[key].append({"role": "user", "content": user_msg})
    data[key].append({"role": "assistant", "content": bot_msg})
    if len(data[key]) > 20:
        data[key] = data[key][-20:]
    try:
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save conversation: {e}")


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
