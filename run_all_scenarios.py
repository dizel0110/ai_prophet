"""Run all 4 demo scenarios and save results."""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ["PYTHONPATH"] = os.path.dirname(__file__)

from dotenv import load_dotenv
load_dotenv()

SCENARIOS_DIR = "docs/kaggle/scenarios"
os.makedirs(SCENARIOS_DIR, exist_ok=True)

scenarios = [
    {
        "name": "01_lower_back_pain",
        "title": "Lower Back Pain — Desk Worker",
        "complaint": "Lower back pain radiating to right leg for 3 months. Works desk job 8h/day. Sharp pain when bending forward. No chronic conditions.",
        "age": 35, "gender": "male",
        "photos": ["data/test_photos/posture_back.jpg"],
        "videos": [],
    },
    {
        "name": "02_neck_tension",
        "title": "Neck Tension — Office Worker",
        "complaint": "Chronic neck and shoulder tension. Headaches at the end of day. Stiffness when turning head to the right. Works on laptop. Stress-related.",
        "age": 28, "gender": "female",
        "photos": ["data/test_photos/posture_neck.jpg"],
        "videos": [],
    },
    {
        "name": "03_shoulder_pain",
        "title": "Shoulder Pain — Swimmer",
        "complaint": "Right shoulder pain during overhead movements. Swims 3x/week. Clicking sensation in right shoulder. Mild rotator cuff tendinitis diagnosed.",
        "age": 42, "gender": "male",
        "photos": ["data/test_photos/posture_shoulders.jpg"],
        "videos": [],
    },
    {
        "name": "04_stress_insomnia",
        "title": "Stress & Insomnia — Burnout Recovery",
        "complaint": "Difficulty sleeping, waking up tired. General muscle tension, especially in upper back. Work burnout. No pain, just needs relaxation and stress relief.",
        "age": 30, "gender": "female",
        "photos": [],
        "videos": [],
    },
]

async def run_scenario(scenario):
    from core.adk.workflow import run_massage_consultation_direct

    full_text = f"Age: {scenario['age']}, Gender: {scenario['gender']}. Complaint: {scenario['complaint']}"
    photo_paths = scenario["photos"]
    video_frames = scenario["videos"]

    print(f"\n{'='*60}")
    print(f"SCENARIO: {scenario['title']}")
    print(f"{'='*60}")

    events = await run_massage_consultation_direct(
        chat_id=999, user_message=full_text,
        photo_paths=photo_paths, video_frames_paths=video_frames,
    )

    return events

async def main():
    for s in scenarios:
        try:
            events = await run_scenario(s)
            # Find report
            report = ""
            for e in reversed(events):
                if e["author"] == "final_synthesis_agent":
                    report = e["content"]
                    break
            if not report and events:
                report = events[-1]["content"]

            # Save full output
            output = {
                "scenario": s["title"],
                "complaint": s["complaint"],
                "events": events,
                "report": report,
            }
            path = os.path.join(SCENARIOS_DIR, f"{s['name']}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            # Also save readable summary
            summary_path = os.path.join(SCENARIOS_DIR, f"{s['name']}.md")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(f"# {s['title']}\n\n")
                f.write(f"**Complaint:** {s['complaint']}\n\n")
                f.write(f"**Photos:** {s['photos'] or 'None'}\n\n")
                f.write(f"## Agent Responses\n\n")
                for e in events:
                    f.write(f"### {e['author']}\n\n{e['content']}\n\n")
                f.write(f"## Final Report\n\n{report}\n\n")

            print(f"✅ Saved: {s['name']}")
        except Exception as ex:
            import traceback
            print(f"❌ {s['name']}: {ex}")
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("ALL DONE")
    print(f"{'='*60}")

asyncio.run(main())
