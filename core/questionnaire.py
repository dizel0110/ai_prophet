import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "questionnaire_steps.json")

QUESTIONNAIRE_STEPS = []
QUESTIONNAIRE_STEPS_OPTIONAL = []


def load_steps():
    global QUESTIONNAIRE_STEPS, QUESTIONNAIRE_STEPS_OPTIONAL
    if not os.path.exists(CONFIG_PATH):
        return
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        QUESTIONNAIRE_STEPS = [s for s in data if s.get("required", False)]
        QUESTIONNAIRE_STEPS_OPTIONAL = [s for s in data if not s.get("required", False)]
    except Exception:
        QUESTIONNAIRE_STEPS = []
        QUESTIONNAIRE_STEPS_OPTIONAL = []


load_steps()


def get_step_keys():
    """All possible field keys across all steps and their children."""
    keys = set()
    for step in QUESTIONNAIRE_STEPS + QUESTIONNAIRE_STEPS_OPTIONAL:
        if step["type"] == "group":
            for child in step.get("children", []):
                keys.add(child["key"])
        else:
            keys.add(step["key"])
    return keys


@dataclass
class MassageQuestionnaire:
    # Personal
    full_name: str = ""
    age: int = 0
    gender: str = ""
    phone: str = ""
    height: int = 0
    weight: int = 0

    # Complaints
    complaints: str = ""
    pain_location: str = ""
    pain_type: str = ""
    pain_duration: str = ""
    pain_radiation: str = ""

    # Health
    chronic_diseases: List[str] = field(default_factory=list)
    allergies: str = ""
    medications: str = ""
    trauma_surgery_history: str = ""
    pain_threshold: str = ""
    ticklish_areas: str = ""
    skin_condition: str = ""
    vascular_issues: str = ""
    widow_hump: str = ""
    doctor_diagnosis: str = ""

    # Vitals
    blood_pressure_systolic: int = 0
    blood_pressure_diastolic: int = 0
    pulse: int = 0
    body_temperature: float = 0.0

    # Contraindications
    contraindications_absolute: List[str] = field(default_factory=list)
    is_pregnant: bool = False
    has_fever: bool = False
    has_inflammation: bool = False
    recent_surgery: str = ""
    informed_consent: bool = False

    # Lifestyle
    work_type: str = ""
    work_schedule: str = ""
    physical_activity: str = ""
    daily_steps: int = 0
    sleep_hours: int = 0
    stress_level: int = 0

    # Extra
    additional_info: str = ""

    # Backward compat
    has_hypertension: bool = False
    has_diabetes: bool = False
    has_heart_disease: bool = False
    has_varicose_veins: bool = False
    has_thrombosis: bool = False
    has_oncology: bool = False
    has_skin_disease: bool = False
    has_allergies: bool = False
    allergies_description: str = ""
    pain_type_old: str = ""
    pain_duration_old: str = ""

    def to_text(self) -> str:
        lines = []

        lines.append("=== ЛИЧНЫЕ ДАННЫЕ ===")
        if self.full_name: lines.append(f"ФИО: {self.full_name}")
        if self.age: lines.append(f"Возраст: {self.age}")
        if self.gender: lines.append(f"Пол: {self.gender}")
        if self.phone: lines.append(f"Телефон: {self.phone}")
        if self.height: lines.append(f"Рост: {self.height} см")
        if self.weight: lines.append(f"Вес: {self.weight} кг")
        lines.append("")

        lines.append("=== ЖАЛОБЫ ===")
        if self.complaints: lines.append(f"Описание: {self.complaints}")
        if self.pain_location: lines.append(f"Локализация: {self.pain_location}")
        if self.pain_type or self.pain_type_old: lines.append(f"Тип боли: {self.pain_type or self.pain_type_old}")
        if self.pain_duration or self.pain_duration_old: lines.append(f"Длительность: {self.pain_duration or self.pain_duration_old}")
        if self.pain_radiation: lines.append(f"Иррадиация: {self.pain_radiation}")
        lines.append("")

        lines.append("=== ХРОНИЧЕСКИЕ ЗАБОЛЕВАНИЯ ===")
        diseases = list(self.chronic_diseases)
        for attr, name in [
            ("has_hypertension", "Гипертония"), ("has_diabetes", "Диабет"),
            ("has_heart_disease", "ССЗ"), ("has_varicose_veins", "Варикоз"),
            ("has_thrombosis", "Тромбоз"), ("has_oncology", "Онкология"),
            ("has_skin_disease", "Кожные заболевания")
        ]:
            if getattr(self, attr, False) and name not in diseases:
                diseases.append(name)
        lines.append(f"Заболевания: {', '.join(diseases) if diseases else 'Не указаны'}")
        if self.allergies or self.has_allergies:
            lines.append(f"Аллергии: {self.allergies or self.allergies_description}")
        if self.medications: lines.append(f"Лекарства: {self.medications}")
        if self.trauma_surgery_history: lines.append(f"Травмы/операции: {self.trauma_surgery_history}")
        if self.doctor_diagnosis: lines.append(f"Диагноз врача: {self.doctor_diagnosis}")
        lines.append("")

        lines.append("=== ВИТАЛЬНЫЕ ПОКАЗАТЕЛИ ===")
        if self.blood_pressure_systolic or self.blood_pressure_diastolic:
            lines.append(f"АД: {self.blood_pressure_systolic}/{self.blood_pressure_diastolic}")
        if self.pulse: lines.append(f"Пульс: {self.pulse} уд/мин")
        if self.body_temperature: lines.append(f"Температура: {self.body_temperature}°C")
        lines.append("")

        lines.append("=== ПРОТИВОПОКАЗАНИЯ ===")
        if self.contraindications_absolute:
            lines.append(f"Абсолютные: {', '.join(self.contraindications_absolute)}")
        lines.append(f"Беременность: {'Да' if self.is_pregnant else 'Нет'}")
        lines.append(f"Температура/лихорадка: {'Да' if self.has_fever else 'Нет'}")
        lines.append(f"Воспаление/обострение: {'Да' if self.has_inflammation else 'Нет'}")
        if self.recent_surgery: lines.append(f"Недавние операции: {self.recent_surgery}")
        lines.append(f"Информированное согласие: {'✅ Да' if self.informed_consent else 'Нет'}")
        lines.append("")

        lines.append("=== ОБРАЗ ЖИЗНИ ===")
        if self.work_type: lines.append(f"Тип работы: {self.work_type}")
        if self.work_schedule: lines.append(f"График: {self.work_schedule}")
        if self.physical_activity: lines.append(f"Физ. активность: {self.physical_activity}")
        if self.daily_steps: lines.append(f"Шаги/день: {self.daily_steps}")
        if self.sleep_hours: lines.append(f"Сон: {self.sleep_hours} ч")
        if self.stress_level: lines.append(f"Стресс (0-10): {self.stress_level}")
        lines.append("")

        if self.pain_threshold: lines.append(f"Болевой порог: {self.pain_threshold}")
        if self.ticklish_areas: lines.append(f"Зоны щекотки: {self.ticklish_areas}")
        if self.skin_condition: lines.append(f"Кожа: {self.skin_condition}")
        if self.vascular_issues: lines.append(f"Сосуды: {self.vascular_issues}")
        if self.widow_hump: lines.append(f"Вдовий горбик: {self.widow_hump}")

        if self.additional_info:
            lines.append("")
            lines.append("=== ДОПОЛНИТЕЛЬНО ===")
            lines.append(self.additional_info)

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        valid_keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in valid_keys})
