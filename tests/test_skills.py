"""Tests for core/adk/skills.py — ADK Agent Skills integration.

Covers: skill definitions, frontmatter, resources, SkillToolset, agent attachment."""
import asyncio
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSkillDefinitions:
    """Verify the three ADK Skills are correctly defined."""

    def test_skills_module_imports(self):
        from core.adk.skills import (
            massage_tech_skill,
            anatomy_knowledge_skill,
            music_therapy_skill,
            massage_skills_toolset,
        )
        assert massage_tech_skill is not None
        assert anatomy_knowledge_skill is not None
        assert music_therapy_skill is not None
        assert massage_skills_toolset is not None

    def test_all_skills_have_valid_names(self):
        from core.adk.skills import massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill
        for skill in [massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill]:
            assert skill.name, f"Skill missing name"
            # Names must be lowercase kebab-case per ADK spec
            assert skill.name == skill.name.lower(), f"Skill name '{skill.name}' must be lowercase"
            assert skill.name.replace("-", "").isalnum(), f"Skill name '{skill.name}' must be kebab-case"

    def test_all_skills_have_descriptions(self):
        from core.adk.skills import massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill
        for skill in [massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill]:
            assert skill.description, f"Skill '{skill.name}' missing description"
            assert len(skill.description) > 20, f"Skill '{skill.name}' description too short"

    def test_all_skills_have_instructions(self):
        from core.adk.skills import massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill
        for skill in [massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill]:
            assert skill.instructions, f"Skill '{skill.name}' missing instructions"
            assert len(skill.instructions) > 100, f"Skill '{skill.name}' instructions too short"

    def test_all_skills_have_resources(self):
        from core.adk.skills import massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill
        for skill in [massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill]:
            assert skill.resources is not None, f"Skill '{skill.name}' missing resources"
            assert len(skill.resources.references) >= 1, f"Skill '{skill.name}' should have at least 1 reference"

    def test_massage_tech_references(self):
        from core.adk.skills import massage_tech_skill
        refs = massage_tech_skill.resources.references
        assert "technique-categories.txt" in refs
        assert "contraindication-checklist.txt" in refs
        assert "massage" in refs["technique-categories.txt"].lower()

    def test_anatomy_references(self):
        from core.adk.skills import anatomy_knowledge_skill
        refs = anatomy_knowledge_skill.resources.references
        assert "common-pain-patterns.txt" in refs
        assert "back" in refs["common-pain-patterns.txt"].lower() or "pain" in refs["common-pain-patterns.txt"].lower()

    def test_music_references(self):
        from core.adk.skills import music_therapy_skill
        refs = music_therapy_skill.resources.references
        assert "music-genre-effects.txt" in refs
        assert "ambient" in refs["music-genre-effects.txt"].lower() or "cortisol" in refs["music-genre-effects.txt"].lower()

    def test_frontmatter_has_valid_structure(self):
        from core.adk.skills import massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill
        from google.adk.skills import models
        for skill in [massage_tech_skill, anatomy_knowledge_skill, music_therapy_skill]:
            assert isinstance(skill.frontmatter, models.Frontmatter)
            assert skill.frontmatter.name == skill.name
            assert skill.frontmatter.description == skill.description


class TestSkillToolset:
    """Verify the SkillToolset is correctly constructed."""

    def test_toolset_imports(self):
        from core.adk.skills import massage_skills_toolset
        from google.adk.tools.skill_toolset import SkillToolset
        assert isinstance(massage_skills_toolset, SkillToolset)

    def test_toolset_creates_tools(self):
        from core.adk.skills import massage_skills_toolset
        tools = asyncio.run(massage_skills_toolset.get_tools())
        tool_names = [t.name for t in tools]
        assert "list_skills" in tool_names
        assert "load_skill" in tool_names
        assert "load_skill_resource" in tool_names

    def test_toolset_lists_skills(self):
        from core.adk.skills import massage_skills_toolset
        tools = asyncio.run(massage_skills_toolset.get_tools())
        list_skill_tool = next((t for t in tools if t.name == "list_skills"), None)
        assert list_skill_tool is not None
        assert list_skill_tool.description is not None


class TestAgentAttachment:
    """Verify skills are attached to agents."""

    def test_technique_expert_has_skills(self):
        from core.adk.agents import technique_expert_agent
        from google.adk.tools.skill_toolset import SkillToolset
        has_toolset = any(isinstance(t, SkillToolset) for t in technique_expert_agent.tools)
        assert has_toolset, "technique_expert_agent should have SkillToolset in tools"

    def test_technique_expert_has_mcp_tools(self):
        from core.adk.agents import technique_expert_agent
        from google.adk.tools.function_tool import FunctionTool
        mcp_tools = [t for t in technique_expert_agent.tools if isinstance(t, FunctionTool)]
        assert len(mcp_tools) >= 3, "Should have at least 3 FunctionTools (web_search + 2 MCP)"
