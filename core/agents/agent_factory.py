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
    client_memory: str = ""
    communication_schema: Optional[dict] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["__type__"] = "DynamicSpecialist"
        if self.communication_schema is not None:
            d["communication_schema"] = self.communication_schema
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DynamicSpecialist":
        d.pop("__type__", None)
        schema = d.pop("communication_schema", None)
        valid = {k: v for k, v in d.items() if k in cls.__annotations__}
        sp = cls(**valid)
        sp.communication_schema = schema
        return sp


UNIVERSAL_CONSULTANT_NAME = "Мастер-консультант"
UNIVERSAL_CONSULTANT_ROLE = "Главный гид по платформе и специалистам"
UNIVERSAL_CONSULTANT_SYSTEM_PROMPT = """Ты — Мастер-консультант, главный гид по платформе AI Prophet и массажному салону.

Твоя экспертиза:
• Все услуги салона: классический, спортивный, тайский, стоун-терапия, медовый, бамбуковый, антицеллюлитный, лимфодренажный массаж
• AI-консультация — команда из 5 агентов: Анкетолог, Визуальный Диагност, Специалист по движениям, Эксперт по техникам, Финальный Эксперт
• Создание новых ИИ-специалистов под любую задачу
• Музыка для массажа — 8 жанров: Ambient, Классика, Природа, Jazz, Спа, Тайский, Акустика, Бины
• Запись на сеанс через форму в Mini App или WhatsApp

Что ты делаешь:
1. Отвечаешь на вопросы об услугах, ценах, специалистах
2. Помогаешь понять, какой специалист или услуга нужны клиенту
3. Направляешь к профильным ИИ-специалистам
4. Включаешь музыку для массажа
5. Запускаешь AI-консультацию
6. Открываешь запись на сеанс

Ты можешь выполнять действия. Для этого добавь в конце ответа один или несколько маркеров:

[ACTION: open_specialist, "Имя специалиста"] — открыть чат с другим ИИ-специалистом
[ACTION: play_music, "жанр"] — включить музыку (ambient, classic, nature, jazz, spa, thai, acoustic, binaural)
[ACTION: start_consultation] — запустить AI-диагностику (анкетирование + 5 агентов)
[ACTION: go_booking] — открыть запись на сеанс

Примеры использования:
— "Сейчас я подключу специалиста по движениям. [ACTION: open_specialist, "Специалист по движениям"]"
— "Включу расслабляющий эмбиент. [ACTION: play_music, "ambient"]"
— "Давай проведём диагностику. [ACTION: start_consultation]"
— "Записываю на сеанс. [ACTION: go_booking]"

Используй маркеры когда клиент явно просит переключиться на другого специалиста, включить музыку, пройти консультацию или записаться. Не используй маркеры если клиент просто спрашивает информацию.

Важно: НЕ ставь диагнозы, НЕ назначай лекарства. Если нужен профильный специалист — предложи его. Стиль: дружелюбный, заботливый, на "ты". Кратко и по делу.
ВАЖНО: Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы."""

UNIVERSAL_CONSULTANT_SKILLS = "массаж, AI-консультация, подбор специалистов, навигация по платформе, музыка для массажа"

# Встроенные агенты из мульти-агентной системы как чат-специалисты
BUILT_IN_AGENTS = [
    {
        "name": "Визуальный Диагност",
        "role": "Анализ фото осанки и спины",
        "system_prompt": "Ты — Визуальный Диагност, эксперт по визуальной диагностике опорно-двигательного аппарата. По фотографиям спины, позвоночника и осанки клиента ты определяешь: наличие сколиоза, кифоза, лордоза, асимметрию плеч, лопаток, таза, мышечное напряжение или атрофию. Оцениваешь выраженность проблем (лёгкая/средняя/тяжёлая). Клиент может прислать тебе фото для оценки. Если фото нет — задавай наводящие вопросы, чтобы понять, на что обратить внимание. НЕ выходи за рамки визуальной диагностики. НЕ назначай массаж и НЕ давай советов по техникам. Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы.",
        "skills": "визуальная диагностика, осанка, сколиоз, мышечное напряжение",
        "built_in": True,
        "badge": "🤖",
    },
    {
        "name": "Специалист по движениям",
        "role": "Анализ видео походки и движений",
        "system_prompt": "Ты — Специалист по движениям. Анализируешь движения клиента по видео и описанию. Оцениваешь: симметричность движений, объём движений в суставах, ограничения подвижности, компенсаторные паттерны. Клиент может прислать видео для оценки. Если видео нет — задавай вопросы о походке, наклонах, поворотах, боли при движении. НЕ выходи за рамки анализа движений. НЕ ставь диагнозы. НЕ назначай массаж. Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы.",
        "skills": "биомеханика, анализ движений, походка, подвижность суставов",
        "built_in": True,
        "badge": "🤖",
    },
    {
        "name": "Анкетолог",
        "role": "Анализ анкеты и противопоказаний",
        "system_prompt": "Ты — Анкетолог массажного салона. Анализируешь медицинские анкеты клиентов. Выявляешь противопоказания к массажу: онкология, тромбоз, острые воспаления, кожные заболевания, беременность, температура, гипертония, варикоз. Оцениваешь факторы риска и даёшь рекомендации по предосторожностям. Если клиент не заполнил анкету — проведи устный опрос по стандартным пунктам (возраст, здоровье, аллергии, лекарства). НЕ анализируй фото или видео — работай ТОЛЬКО с текстом. Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы.",
        "skills": "анализ анкет, противопоказания, факторы риска, медицинские показания",
        "built_in": True,
        "badge": "🤖",
    },
    {
        "name": "Эксперт по техникам",
        "role": "Подбор техник массажа",
        "system_prompt": "Ты — Эксперт по техникам массажа. На основе данных о клиенте (жалобы, здоровье, предпочтения) ты рекомендуешь конкретные техники массажа. Техники: классический, спортивный, лимфодренажный, антицеллюлитный, точечный, миофасциальный, стоун-терапия, тайский, баночный, медовый. Для каждой указываешь показания и ожидаемый эффект. Консультируй клиента, помогай выбрать подходящую технику. НЕ ставь диагнозов и НЕ назначай медикаментов. Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы.",
        "skills": "классический, спортивный, лимфодренаж, стоун-терапия, тайский, баночный массаж",
        "built_in": True,
        "badge": "🤖",
    },
    {
        "name": "Финальный Эксперт",
        "role": "Итоговое заключение и рекомендации",
        "system_prompt": "Ты — Финальный Эксперт массажного салона AI Prophet. Ты получаешь всю информацию о клиенте и даёшь ОКОНЧАТЕЛЬНОЕ ЗАКЛЮЧЕНИЕ в формате: 1) СТАТУС КЛИЕНТА: Допущен / С ограничениями / Не допущен, 2) ПРИЧИНА, 3) РЕКОМЕНДОВАННЫЕ ТЕХНИКИ, 4) ЗОНЫ ВНИМАНИЯ, 5) ПРОТИВОПОКАЗАНИЯ, 6) СЕАНСЫ. Если данных мало — задавай вопросы, чтобы сформировать полную картину. Будь максимально конкретным и профессиональным. Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы.",
        "skills": "синтез данных, финальное заключение, рекомендации, план лечения",
        "built_in": True,
        "badge": "🤖",
    },
]


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
        if name == UNIVERSAL_CONSULTANT_NAME or role_description == UNIVERSAL_CONSULTANT_ROLE:
            specialist = DynamicSpecialist(
                name=UNIVERSAL_CONSULTANT_NAME,
                role_description=UNIVERSAL_CONSULTANT_ROLE,
                system_prompt=UNIVERSAL_CONSULTANT_SYSTEM_PROMPT,
                skills=UNIVERSAL_CONSULTANT_SKILLS,
                created_at=time.time(),
                chat_id=chat_id,
            )
            _save_specialist(specialist)
            return specialist

        system = "Ты — создатель экспертов. Отвечай только в формате JSON. На языке пользователя (по умолчанию русский). Без иероглифов."
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
            '    • что НЕЛЬЗЯ делать (ставить диагнозы, назначать лекарства, выходить за рамки своей роли)\n'
            '    • стиль общения (профессиональный, заботливый, понятный)\n'
            '    • ВАЖНО: отвечай на языке пользователя, без китайских иероглифов\n\n'
            'Пример: {"name": "Мастер стоун-терапии", "role": "Специалист по массажу горячими камнями", "skills": "стоун-терапия, терморегуляция, расслабление мышц, работа с энергетическими центрами", "system_prompt": "Ты — Мастер стоун-терапии с 8-летним опытом. Узнай у клиента: есть ли проблемы с давлением, кожей, варикозом. Рекомендуй стоун-терапию при мышечном напряжении, стрессе. Не назначай медицинских процедур. Общайся спокойно и уверенно. НЕ выходи за рамки стоун-терапии — если вопрос не по твоей теме, направь к другому специалисту. Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы."}\n\n'
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
                system_prompt=sp if sp else f"Ты — {data.get('name', role_description[:30])}. {data.get('role', role_description)}. Навыки: {data.get('skills', '')}. Консультируй клиента по своей специализации, задавай уточняющие вопросы, направляй в массажный салон AI Prophet. Не ставь медицинских диагнозов. Общайся профессионально и заботливо. Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы.",
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
                system_prompt=f"Ты — {fallback_name}. Твоя роль: {fallback_role}. Консультируй клиента, задавай вопросы, направляй в массажный салон. Не ставь диагнозов. Отвечай на языке пользователя. По умолчанию — русский. НЕ используй китайские иероглифы.",
                skills="",
                created_at=time.time(),
                chat_id=chat_id,
            )

        # Generate communication schema from role
        specialist.communication_schema = cls._generate_schema(specialist)

        _save_specialist(specialist)
        return specialist

    @classmethod
    def _generate_schema(cls, specialist: DynamicSpecialist) -> Optional[dict]:
        if specialist.name == UNIVERSAL_CONSULTANT_NAME:
            return None
        default_schema = {
            "required": [
                {"key": "complaint", "label": "Основная жалоба / запрос", "type": "text"}
            ],
            "optional": [
                {"key": "details", "label": "Подробности", "type": "text"}
            ]
        }
        prompt = f"""Специалист: "{specialist.name}"
Роль: "{specialist.role_description}"

Сгенерируй структуру общения для этого специалиста — какие поля обязательны и необязательны для сбора информации перед консультацией.

Допустимые типы полей: text, number, select, bool, photo, video
Для select обязательно укажи список options.

Ответь ТОЛЬКО JSON без пояснений:
{{
  "required": [
    {{"key": "поле1", "label": "Вопрос пользователю", "type": "text"}},
    ...
  ],
  "optional": [
    {{"key": "поле2", "label": "Вопрос пользователю", "type": "select", "options": ["вар1","вар2"]}},
    ...
  ]
}}

Минимум 1 required, максимум 5 required + 5 optional. На русском языке."""
        try:
            text = cls._call_llm(prompt, "Ты — конструктор анкет. Отвечай только JSON.")
            if not text:
                return default_schema
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                if data.get("required") or data.get("optional"):
                    return data
        except Exception:
            pass
        return default_schema

    @classmethod
    def _extract_memory(cls, text: str) -> str:
        facts = []
        patterns = [
            (r"(?:меня зовут|my name is|я\s+)(\w+)", "Имя клиента"),
            (r"(?:мне\s+)(\d+)\s*(?:лет|года|год)", "Возраст"),
            (r"(?:я\s+)(мужчина|женщина|парень|девушка|male|female)", "Пол"),
            (r"(?:болит|беспокоит|жалуюсь)\s+(?:на\s+)?(.+?)(?:\.|,|$)", "Жалоба"),
            (r"(?:спина|шея|поясница|шейный|грудной|поясничный)", "Локация боли"),
            (r"(?:аллерги|противопоказан|нельзя|беременн|давление|сердц|диабет|онколог|варикоз|грыж|травм)", "Здоровье"),
        ]
        text_lower = text.lower()
        for pat, label in patterns:
            import re
            m = re.search(pat, text_lower)
            if m:
                val = m.group(1).strip().capitalize() if m.lastindex else m.group(0).strip().capitalize()
                facts.append(f"{label}: {val[:60]}")
        return "; ".join(facts) if facts else ""

    @classmethod
    def _merge_memory(cls, old_memory: str, new_facts: str) -> str:
        if not new_facts:
            return old_memory
        if not old_memory:
            return new_facts
        old_parts = set(p.strip() for p in old_memory.split(";"))
        new_parts = [p.strip() for p in new_facts.split(";") if p.strip() not in old_parts]
        if not new_parts:
            return old_memory
        return old_memory + "; " + "; ".join(new_parts)

    @classmethod
    def chat(cls, chat_id: int, specialist: DynamicSpecialist, user_message: str, user_context: str = "") -> AgentResult:
        cls._ensure_clients()
        history = _load_conversation(chat_id, specialist.name)

        # Build context with memory
        memory_block = ""
        if specialist.client_memory:
            memory_block = f"\n[Память о клиенте: {specialist.client_memory}]\n\n"
        if user_context:
            memory_block += f"\n[Данные клиента из анкеты:\n{user_context}]\n\n"

        # Gemini first — лучше следует system prompt
        if cls._gemini_client:
            for model in FALLBACK_MODELS[:2]:
                try:
                    ctx = specialist.system_prompt + memory_block
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
                        specialist.client_memory = cls._merge_memory(specialist.client_memory, cls._extract_memory(user_message))
                        _save_specialist(specialist)
                        _save_conversation(chat_id, specialist.name, user_message, resp.text.strip())
                        return AgentResult(f"s_{chat_id}", specialist.name, resp.text.strip())
                    else:
                        logger.warning(f"Gemini specialist chat {model}: empty response (safety filter?)")
                except Exception as e:
                    logger.warning(f"Gemini specialist chat {model}: {e}")

        # HF fallback — обычно Qwen
        if cls._hf_token:
            try:
                msgs = [{"role": "system", "content": specialist.system_prompt + memory_block}]
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
                    specialist.client_memory = cls._merge_memory(specialist.client_memory, cls._extract_memory(user_message))
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
    created = [DynamicSpecialist.from_dict(s) for s in data.get(str(chat_id), [])]
    # Merge built-in agents, avoiding duplicates
    existing_names = {s.name.lower() for s in created}
    for ba in BUILT_IN_AGENTS:
        if ba["name"].lower() not in existing_names:
            created.append(DynamicSpecialist(
                name=ba["name"],
                role_description=ba["role"],
                system_prompt=ba["system_prompt"],
                skills=ba["skills"],
                created_at=0,
                chat_id=chat_id,
            ))
    return created


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
            # Clean up conversation
            conv = {}
            if os.path.exists(CONVERSATIONS_FILE):
                try:
                    with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                        conv = json.load(f)
                except Exception:
                    pass
            conv.pop(f"{chat_id}_{name}", None)
            try:
                with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
                    json.dump(conv, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            return True
    return False


def update_specialist(chat_id: int, old_name: str, new_name: str = "", new_role: str = "") -> bool:
    data = _load_all_specialists()
    key = str(chat_id)
    if key not in data:
        return False
    lst = data[key]
    for s in lst:
        if s.get("name", "").lower() == old_name.lower():
            if new_name:
                s["name"] = new_name
                s["role_description"] = s.get("role_description", "").replace(old_name, new_name)
                if s.get("system_prompt", "").startswith("Ты — " + old_name):
                    s["system_prompt"] = s["system_prompt"].replace("Ты — " + old_name, "Ты — " + new_name, 1)
            if new_role:
                s["role_description"] = new_role
            _write_specialists(data)
            # Rename conversation key if name changed
            if new_name and new_name.lower() != old_name.lower():
                conv = {}
                if os.path.exists(CONVERSATIONS_FILE):
                    try:
                        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                            conv = json.load(f)
                    except Exception:
                        pass
                old_key = f"{chat_id}_{old_name}"
                new_key = f"{chat_id}_{new_name}"
                if old_key in conv:
                    conv[new_key] = conv.pop(old_key)
                    try:
                        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
                            json.dump(conv, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
            return True
    return False
