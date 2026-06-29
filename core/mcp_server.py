"""
Lightweight MCP (Model Context Protocol) server for massage AI tools.

This server runs as a subprocess and exposes tools over stdio transport
using the Model Context Protocol. The ProphetMCPClient connects to it from
the main process.

This demonstrates MCP protocol integration for the Kaggle capstone:
- Server defines tools with schema
- Client connects via stdio transport
- Communication uses MCP's JSON-RPC protocol
"""
import logging
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Create the MCP server instance
# FastMCP handles all MCP protocol details (JSON-RPC, tool discovery, invocation)
mcp_server = FastMCP("massage-ai-mcp-server")


@mcp_server.tool()
def fetch_url(url: str) -> str:
    """Fetch content from a URL for research purposes.

    Used by the Technique Expert to research massage techniques,
    verify contraindications, and gather additional context.

    Args:
        url: The full URL to fetch (must be http/https)
    Returns:
        Text content of the page (first 8000 chars)
    """
    import requests
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "AIProphet-MCP/1.0 (massage consultation agent)"
        })
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type or "text/plain" in content_type:
            text = resp.text[:8000]
            return f"URL: {url}\nStatus: {resp.status_code}\nContent:\n{text}"
        return f"URL: {url}\nStatus: {resp.status_code}\nContent-Type: {content_type}\n[Non-text content — skipped]"
    except Exception as e:
        return f"URL: {url}\nError: {e}"


@mcp_server.tool()
def search_massage_knowledge(query: str) -> str:
    """Search massage therapy knowledge base for techniques, contraindications, anatomy.

    Queries a curated massage knowledge base covering classical techniques,
    myofascial release, sports massage, lymphatic drainage, Thai massage,
    hot stone therapy, cupping, and their specific indications/contraindications.

    Args:
        query: Search query about massage techniques or conditions
    Returns:
        Relevant knowledge entries matching the query
    """
    query_lower = query.lower()

    # Curated knowledge base
    knowledge_base = {
        "classical massage": (
            "Classical (Swedish) massage uses long gliding strokes, kneading, "
            "friction, tapping, and vibration. Indications: muscle tension, stress, "
            "poor circulation, general relaxation. Duration: 30-90 min. "
            "Contraindications: acute inflammation, fever, skin infections, thrombosis."
        ),
        "deep tissue": (
            "Deep tissue massage targets deeper muscle layers and fascia. "
            "Uses slow, firm pressure and friction strokes. "
            "Indications: chronic muscle tension, adhesions, postural issues, "
            "myofascial pain. Duration: 60-90 min. "
            "Contraindications: acute injuries, inflammation, osteoporosis, blood thinners."
        ),
        "myofascial release": (
            "Myofascial release applies sustained pressure to myofascial connective "
            "tissue restrictions. Indications: chronic pain, fibromyalgia, "
            "fascial restrictions, post-surgical adhesions. "
            "Duration: 30-60 min per area. "
            "Contraindications: malignant tumors, fractures, acute RA, deep vein thrombosis."
        ),
        "sports massage": (
            "Sports massage focuses on muscles used in specific sports. "
            "Includes pre-event (stimulating), post-event (flushing), "
            "and maintenance (recovery) protocols. "
            "Indications: athletic recovery, injury prevention, improved range of motion. "
            "Duration: 30-90 min. "
            "Contraindications: acute sports injuries (first 48h), fever, infection."
        ),
        "lymphatic drainage": (
            "Manual lymphatic drainage uses light, rhythmic, pumping movements "
            "to stimulate lymph flow. Indications: edema, lymphedema post-surgery, "
            "detoxification, immune support. Duration: 45-75 min. "
            "Contraindications: acute infections, heart failure, thrombosis, malignant tumors."
        ),
        "hot stone": (
            "Hot stone massage uses smooth, heated basalt stones placed on key body points "
            "and used as massage tools. Indications: deep relaxation, muscle tension, "
            "stress relief, improved circulation. Duration: 60-90 min. "
            "Contraindications: varicose veins (avoid direct heat), diabetes with neuropathy, "
            "pregnancy (first trimester), heart disease, recent surgery."
        ),
        "thai massage": (
            "Thai massage combines assisted stretching, compression, and joint mobilization. "
            "Performed on a mat, client wears loose clothing. "
            "Indications: stiffness, limited flexibility, stress, energy blockages. "
            "Duration: 60-120 min. "
            "Contraindications: recent fractures, severe osteoporosis, "
            "herniated disc (acute phase), pregnancy, cardiovascular conditions."
        ),
        "cupping": (
            "Cupping therapy uses suction cups on the skin to increase blood flow. "
            "Can be static (5-15 min) or moving (with oil). "
            "Indications: muscle pain, trigger points, respiratory conditions, cellulite. "
            "Duration: 10-20 min per area. "
            "Contraindications: sunburn, wounds, inflamed skin, pregnancy (abdomen/lower back), "
            "bleeding disorders, anticoagulant medication."
        ),
        "sciatica": (
            "Sciatica massage should focus on piriformis release, gluteal relaxation, "
            "and lumbar paraspinal work. Avoid direct pressure on the sciatic nerve. "
            "Use: gentle gluteal stripping, positional release for piriformis, "
            "and lumbar erector spinae work. "
            "Duration: 45-60 min, 2x per week. "
            "Precautions: avoid deep pressure if acute pain, use sidelying positioning."
        ),
        "pregnancy": (
            "Pregnancy massage uses sidelying positioning with pillow support. "
            "Avoid: deep abdominal work, pressure on low back/ sacrum in first trimester, "
            "vigorous stretching. Safe zones: shoulders, neck, arms, legs (gentle), back. "
            "Indications: back pain, edema, stress, hip pain during pregnancy. "
            "Contraindications: high-risk pregnancy, preeclampsia, placental issues."
        ),
        "contraindications": (
            "ABSOLUTE contraindications (DO NOT massage): malignant tumors, "
            "thrombosis/thrombophlebitis, gangrene, aneurysm, active TB, "
            "osteomyelitis (acute), circulatory/kidney/liver failure stage III, "
            "heart valve defects (decompensated), acute myocardial ischemia, "
            "cerebral sclerosis stage III, AIDS.\n\n"
            "TEMPORARY contraindications (reschedule): fever >37°C, acute infections, "
            "acute inflammation, bleeding, purulent processes, inflamed lymph nodes, "
            "hypertensive/hypotensive crisis, alcohol/drug intoxication.\n\n"
            "Precautions (massage WITH restrictions): varicose veins, osteoporosis, "
            "diabetes, epilepsy, recent surgery (6 weeks+), herniated disc, "
            "chronic fatigue syndrome, fibromyalgia."
        ),
    }

    results = []
    for keyword, info in knowledge_base.items():
        words = keyword.split()
        if any(w in query_lower for w in words) or all(w in query_lower for w in query_lower.split() if len(w) > 3 and w in keyword):
            results.append(f"\n{'='*50}\n{keyword.upper()}\n{'='*50}\n{info}")

    if results:
        return "Knowledge base results:" + "".join(results)
    return (
        f"No exact match for '{query}' in knowledge base.\n"
        f"Available topics: classical massage, deep tissue, myofascial release, "
        f"sports massage, lymphatic drainage, hot stone, Thai massage, cupping, "
        f"sciatica, pregnancy massage, contraindications."
    )


if __name__ == "__main__":
    """Run the MCP server. In production, started as subprocess by ProphetMCPClient."""
    mcp_server.run(transport="stdio")
