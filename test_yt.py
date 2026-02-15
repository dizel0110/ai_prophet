import logging
from duckduckgo_search import DDGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ddg_video_search():
    query = "Pink Floyd best songs audio"
    print(f"🔎 Testing DDG Video Search for: '{query}'...")
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.videos(query, max_results=5))
            
            if results:
                print(f"✅ Success! Found {len(results)} videos.")
                for i, r in enumerate(results, 1):
                    print(f"{i}. {r.get('title')} - {r.get('content')}")
            else:
                print("❌ No videos found via DDG.")
                
    except Exception as e:
        print(f"❌ DDG Error: {e}")

if __name__ == "__main__":
    test_ddg_video_search()
