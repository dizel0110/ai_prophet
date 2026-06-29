"""
ADK Agent Skills for the massage therapy consultation system.

Skills are self-contained units of functionality with progressive disclosure
(L1: metadata → L2: instructions → L3: resources). They're wrapped in a
SkillToolset and passed to agents as tools, letting the agent load detailed
instructions on demand without bloating the context window.

This demonstrates the ADK Agent Skills concept for the Kaggle capstone.

Usage:
    skill_toolset = SkillToolset(
        skills=[massage_tech_skill, anatomy_knowledge_skill],
        additional_tools=[mcp_fetch_url_tool, mcp_search_knowledge_tool],
    )
    agent = Agent(..., tools=[skill_toolset])
"""
import logging
from google.adk.skills import models
from google.adk.tools.skill_toolset import SkillToolset

logger = logging.getLogger(__name__)


# ── Skill: Massage Technique Reference ──────────────────────────────────────
massage_tech_skill = models.Skill(
    frontmatter=models.Frontmatter(
        name="massage-technique-reference",
        description=(
            "Detailed reference about massage techniques: indications, "
            "contraindications, duration, pressure levels, and body positions."
        ),
    ),
    instructions=(
        "You are a massage therapy reference expert.\n\n"
        "Use this skill when you need detailed information about:\n"
        "- Massage techniques (classical, deep tissue, myofascial, sports, Thai, etc.)\n"
        "- Contraindications and precautions for each technique\n"
        "- Recommended session duration and frequency\n"
        "- Client positioning during massage\n"
        "- Pressure levels and adaptation for different body types\n\n"
        "When asked about a technique:\n"
        "1. First describe what the technique is and its primary purpose\n"
        "2. List indications (when to use it)\n"
        "3. List contraindications (when to avoid it)\n"
        "4. Recommend duration, pressure, and positioning\n"
        "5. Mention any special considerations or risks\n\n"
        "If you need current information from the web, use the fetch_url tool.\n"
        "If you need to search the curated knowledge base, use search_massage_knowledge."
    ),
    resources=models.Resources(
        references={
            "technique-categories.txt": (
                "Massage Technique Categories:\n"
                "1. Relaxation: Swedish, classical, aromatherapy\n"
                "2. Therapeutic: deep tissue, myofascial release, trigger point\n"
                "3. Rehabilitative: sports massage, lymphatic drainage, medical\n"
                "4. Energy work: Thai, Shiatsu, reflexology\n"
                "5. Specialized: hot stone, cupping, gua sha, prenatal"
            ),
            "contraindication-checklist.txt": (
                "ABSOLUTE CONTRAINDICATIONS:\n"
                "- Acute thrombosis, phlebitis\n"
                "- Contagious diseases, infections\n"
                "- Severe osteoporosis\n"
                "- Recent fracture or surgery (< 6 weeks)\n"
                "- Malignant tumors at massage site\n"
                "- Acute rheumatoid arthritis flare\n"
                "- Severe cardiovascular conditions\n\n"
                "LOCAL CONTRAINDICATIONS:\n"
                "- Varicose veins\n"
                "- Bruises, cuts, inflammation\n"
                "- Sunburn, rashes, skin infections\n"
                "- Hematomas\n"
                "- Recent scars (< 6 months)"
            ),
        },
    ),
)


# ── Skill: Anatomy & Pathology Knowledge ───────────────────────────────────
anatomy_knowledge_skill = models.Skill(
    frontmatter=models.Frontmatter(
        name="anatomy-pathology-reference",
        description=(
            "Musculoskeletal anatomy reference: muscles, bones, nerves, "
            "and common pathologies relevant to massage therapy."
        ),
    ),
    instructions=(
        "You are an anatomy reference specialist for massage therapists.\n\n"
        "Use this skill when you need to understand:\n"
        "- Muscle origins, insertions, and actions\n"
        "- Nerve pathways and common entrapment sites\n"
        "- Common pain patterns and referred pain\n"
        "- Postural analysis and muscle imbalances\n"
        "- Pathologies affecting the musculoskeletal system\n\n"
        "When analyzing a client's complaint:\n"
        "1. Identify which muscles/joints/nerves are likely involved\n"
        "2. Consider common referred pain patterns\n"
        "3. Check for posture-related contributions\n"
        "4. Assess if pathology is acute or chronic\n"
        "5. Recommend appropriate technique focus areas"
    ),
    resources=models.Resources(
        references={
            "common-pain-patterns.txt": (
                "Common Pain Patterns:\n\n"
                "LOWER BACK:\n"
                "- Muscle strain: dull ache, worse with movement\n"
                "- Disc issues: sharp pain, may radiate to leg\n"
                "- Piriformis syndrome: deep gluteal pain, sciatica-like\n"
                "- Facet joint: pain worse with extension\n\n"
                "NECK & SHOULDER:\n"
                "- Upper trapezius: tension headaches, neck stiffness\n"
                "- Levator scapulae: pain at shoulder angle, limited rotation\n"
                "- Rotator cuff: deep shoulder pain, weakness\n\n"
                "HEAD & JAW:\n"
                "- Tension headache: band-like pressure\n"
                "- TMJ: jaw clicking, facial pain\n"
                "- Cervicogenic: from neck, one-sided"
            ),
        },
    ),
)


# ── Skill: Music Therapy for Massage ───────────────────────────────────────
music_therapy_skill = models.Skill(
    frontmatter=models.Frontmatter(
        name="music-therapy-massage",
        description=(
            "Guidelines for selecting therapeutic music for massage sessions "
            "based on technique type, client condition, and treatment goals."
        ),
    ),
    instructions=(
        "You are a music therapy specialist for massage sessions.\n\n"
        "Use this skill when recommending music for a massage session:\n"
        "1. Consider the technique type (relaxation vs deep tissue vs Thai)\n"
        "2. Consider the client's condition (stress, pain, recovery)\n"
        "3. Match tempo to massage rhythm (slow for relaxation, medium for active)\n"
        "4. Recommend genre, duration, and approximate track count\n\n"
        "Genre guidelines:\n"
        "- Deep tissue / therapeutic: ambient, classical, instrumental\n"
        "- Relaxation / Swedish: nature sounds, ambient, piano\n"
        "- Sports massage: upbeat instrumental, world beats\n"
        "- Thai massage: traditional Thai, pan flute, nature\n"
        "- Hot stone / spa: ambient, ocean waves, zen\n"
        "- Prenatal: gentle classical, lullabies, nature"
    ),
    resources=models.Resources(
        references={
            "music-genre-effects.txt": (
                "Music Genres and Their Therapeutic Effects:\n\n"
                "AMBIENT: Lowers cortisol, reduces anxiety, promotes deep relaxation\n"
                "CLASSICAL: Decreases blood pressure, improves mood (60-80 bpm ideal)\n"
                "NATURE SOUNDS: Masks distracting noise, triggers parasympathetic response\n"
                "JAZZ: Gentle stimulation, good for moderate-tempo sessions\n"
                "WORLD/ETHNIC: Cultural connection, varied rhythms for energetic work\n"
                "BINAURAL BEATS: Potential for altered brainwave states (theta/delta)"
            ),
        },
    ),
)


# ── SkillToolset: bundle all skills together ────────────────────────────────
# The SkillToolset auto-generates three tools that agents can call:
#   list_skills (L1) — returns names + descriptions of all skills
#   load_skill (L2) — loads full instructions of a named skill
#   load_skill_resource (L3) — fetches a reference file by key
#
# This is passed to agents via tools=[massage_skills_toolset].
massage_skills_toolset = SkillToolset(
    skills=[
        massage_tech_skill,
        anatomy_knowledge_skill,
        music_therapy_skill,
    ],
)
