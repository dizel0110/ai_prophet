import logging
import asyncio
import os
from typing import List, Optional, Dict, Any

from core.agents.agent_base import AgentBase
from core.agents.registry import get_all_agents, get_agent_def, get_groups_summary

logger = logging.getLogger(__name__)


class MassageConsultationOrchestrator:
    """
    Запускает полный пайплайн консультации:
      1. Анкетолог    — анализ анкеты (текст)
      2. Виз.Диагност — анализ фото (vision)
      3. Движения     — анализ видео (извлечение кадров)
      4. Техники      — рекомендации техник (текст)
      5. Финальный    — синтез всех данных (текст)
    """
    def __init__(self):
        self.specialists = get_all_agents()
        self.final = AgentBase(**get_agent_def("final_expert"))

    async def run_consultation(
        self,
        questionnaire_text: str,
        photo_paths: Optional[List[str]] = None,
        video_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        results = {}

        # 1. Анкетолог
        logger.info("Агент: Анкетолог")
        qa = self._find("questionnaire_analyst")
        if qa:
            results["questionnaire_analyst"] = (await asyncio.to_thread(qa.process_text, questionnaire_text)).to_dict()

        # 2. Визуальный Диагност (по всем фото)
        diag = self._find("visual_diagnostician")
        if diag and photo_paths:
            results["visual_diagnostician"] = []
            for path in photo_paths:
                r = await asyncio.to_thread(diag.process_vision, questionnaire_text[:300], path)
                results["visual_diagnostician"].append(r.to_dict())

        # 3. Специалист по движениям (по видео — извлекает кадры)
        mov = self._find("movement_specialist")
        if mov and video_paths:
            results["movement_specialist"] = []
            for path in video_paths:
                r = await asyncio.to_thread(mov.process_video_frames, questionnaire_text[:300], path)
                results["movement_specialist"].append(r.to_dict())

        # 4. Эксперт по техникам (собирает все данные)
        tech_ctx = self._build_context("technique_expert", questionnaire_text, results)
        tech = self._find("technique_expert")
        if tech:
            results["technique_expert"] = (await asyncio.to_thread(tech.process_text, tech_ctx)).to_dict()

        # 5. Финальный эксперт
        final_ctx = self._build_context("final_expert", questionnaire_text, results, include_all=True)
        final_result = await asyncio.to_thread(self.final.process_text, final_ctx)
        results["final_expert"] = final_result.to_dict()

        return results

    def _find(self, agent_id: str) -> Optional[AgentBase]:
        for a in self.specialists:
            if a.agent_id == agent_id:
                return a
        return None

    def _build_context(self, target_id: str, questionnaire: str, results: dict, include_all=False) -> str:
        parts = [f"=== ИСХОДНАЯ АНКЕТА ===\n{questionnaire}"]
        order = ["questionnaire_analyst", "visual_diagnostician", "movement_specialist"]
        if include_all:
            order.append("technique_expert")

        for key in order:
            if key not in results:
                continue
            name = get_agent_def(key).get("name", key)
            val = results[key]
            texts = []
            if isinstance(val, list):
                for v in val:
                    texts.append(v.get("content", ""))
            elif isinstance(val, dict):
                texts.append(val.get("content", ""))
            if texts:
                parts.append(f"\n=== {name} ===\n" + "\n".join(texts))

        hints = {
            "technique_expert": "На основе всех данных порекомендуй конкретные техники массажа.",
            "final_expert": "Синтезируй все данные и выдай ОКОНЧАТЕЛЬНОЕ ЗАКЛЮЧЕНИЕ по формату.",
        }
        parts.append(f"\n\n{hints.get(target_id, '')}")
        return "\n".join(parts)


def format_consultation_results(results: dict) -> str:
    """Форматирование результатов для Telegram."""
    lines = ["🧑‍⚕️ *РЕЗУЛЬТАТЫ КОНСУЛЬТАЦИИ*\n"]

    for key, val in results.items():
        if key == "final_expert":
            continue
        name = get_agent_def(key).get("name", key)
        texts = []
        if isinstance(val, list):
            for v in val:
                texts.append(v.get("content", ""))
        elif isinstance(val, dict):
            texts.append(val.get("content", ""))
        content = "\n".join(texts)[:500]
        if content:
            lines.append(f"*{name}:*\n{content}...\n")

    if "final_expert" in results:
        lines.append(f"\n{'═' * 40}")
        lines.append("*📋 ЗАКЛЮЧЕНИЕ ФИНАЛЬНОГО ЭКСПЕРТА:*\n")
        lines.append(results["final_expert"].get("content", ""))

    return "\n".join(lines)
