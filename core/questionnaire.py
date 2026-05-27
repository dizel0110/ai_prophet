from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class MassageQuestionnaire:
    full_name: str = ""
    age: int = 0
    gender: str = ""
    phone: str = ""
    complaints: str = ""
    pain_location: str = ""
    pain_type: str = ""
    pain_duration: str = ""
    chronic_diseases: List[str] = field(default_factory=list)
    has_hypertension: bool = False
    has_diabetes: bool = False
    has_heart_disease: bool = False
    has_varicose_veins: bool = False
    has_thrombosis: bool = False
    has_oncology: bool = False
    has_skin_disease: bool = False
    has_allergies: bool = False
    allergies_description: str = ""
    is_pregnant: bool = False
    has_fever: bool = False
    has_inflammation: bool = False
    recent_surgery: str = ""
    medications: str = ""
    physical_activity: str = ""
    work_type: str = ""
    additional_info: str = ""

    def to_text(self) -> str:
        lines = [
            f"Имя: {self.full_name}", f"Возраст: {self.age}", f"Пол: {self.gender}",
            f"Телефон: {self.phone}", "",
            "=== ЖАЛОБЫ ===",
            f"Описание: {self.complaints}", f"Локализация боли: {self.pain_location}",
            f"Тип боли: {self.pain_type}", f"Длительность: {self.pain_duration}", "",
            "=== ХРОНИЧЕСКИЕ ЗАБОЛЕВАНИЯ ===",
        ]
        diseases = self.chronic_diseases.copy()
        if self.has_hypertension: diseases.append("Гипертония")
        if self.has_diabetes: diseases.append("Диабет")
        if self.has_heart_disease: diseases.append("Сердечно-сосудистые заболевания")
        if self.has_varicose_veins: diseases.append("Варикоз")
        if self.has_thrombosis: diseases.append("Тромбоз")
        if self.has_oncology: diseases.append("Онкология (в анамнезе)")
        if self.has_skin_disease: diseases.append("Кожные заболевания")
        lines.append(f"Заболевания: {', '.join(diseases) if diseases else 'Не указаны'}")
        if self.has_allergies:
            lines.append(f"Аллергии: {self.allergies_description}")
        lines.extend([
            "", "=== ПРОТИВОПОКАЗАНИЯ ===",
            f"Беременность: {'Да' if self.is_pregnant else 'Нет'}",
            f"Температура/воспаление: {'Да' if self.has_fever else 'Нет'}",
            f"Острые воспаления: {'Да' if self.has_inflammation else 'Нет'}",
            f"Недавние операции: {self.recent_surgery or 'Нет'}",
            f"Лекарства: {self.medications or 'Не указаны'}", "",
            "=== ОБРАЗ ЖИЗНИ ===",
            f"Физ. активность: {self.physical_activity}", f"Тип работы: {self.work_type}",
        ])
        if self.additional_info:
            lines.extend(["", "=== ДОПОЛНИТЕЛЬНО ===", self.additional_info])
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        valid_keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in valid_keys})


QUESTIONNAIRE_STEPS = [
    {"key": "full_name", "question": "👤 Как вас зовут?", "type": "text"},
    {"key": "age", "question": "🎂 Сколько вам лет?", "type": "text"},
    {"key": "gender", "question": "🚻 Ваш пол?", "type": "choice", "options": ["Мужской", "Женский"]},
    {"key": "complaints", "question": "💭 На что жалуетесь? Опишите ваши проблемы (боли, напряжение, ограничения)", "type": "text"},
    {"key": "pain_location", "question": "📍 Где именно болит? (шея, спина, поясница, ноги, всё тело)", "type": "text"},
    {"key": "pain_type", "question": "🔥 Какой характер боли?", "type": "choice", "options": ["Острая", "Хроническая/ноющая", "Пульсирующая", "Тянущая", "Другое"]},
    {"key": "pain_duration", "question": "⏳ Как давно беспокоит?", "type": "choice", "options": ["Несколько дней", "Несколько недель", "Несколько месяцев", "Больше года"]},
    {"key": "diseases", "question": "🏥 Есть ли хронические заболевания? (можно выбрать несколько)\nНажми /skip если нет", "type": "multi_choice", "options": ["Гипертония", "Диабет", "Сердечно-сосудистые", "Варикоз", "Тромбоз", "Онкология", "Кожные заболевания", "Другое"]},
    {"key": "contraindications", "question": "⚠️ Есть ли противопоказания?\n- Беременность?\n- Температура/воспаление?\n- Недавние операции?\nНапишите подробно или /skip", "type": "text"},
    {"key": "medications", "question": "💊 Принимаете ли вы лекарства? Какие?", "type": "text"},
    {"key": "lifestyle", "question": "🏃‍♂️ Ваш образ жизни:\n- Какая у вас работа (сидячая/стоячая/физическая)?\n- Занимаетесь спортом?", "type": "text"},
    {"key": "additional", "question": "📝 Что ещё важно знать? (аллергии, пожелания, особые зоны)\nИли /skip", "type": "text"},
]
