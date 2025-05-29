#this is a trial code and the main code used for running is app.py
import os
import json
from dotenv import load_dotenv

load_dotenv()

def main():
    # Load environment variables for API keys
    gemini_api_key  = os.getenv('GEMINI_API_KEY')
    youtube_api_key = os.getenv('YOUTUBE_API_KEY')
    serpapi_api_key = os.getenv('SERPAPI_KEY')

    # Ensure Gemini API key is available
    if not gemini_api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        return

    # Import Google Gemini (Generative AI) SDK
    try:
        import google.generativeai as genai
    except ImportError:
        print("Error: google-generativeai is not installed. Please run:")
        print("  pip install google-generativeai")
        return

    # Configure the Gemini client
    genai.configure(api_key=gemini_api_key)

    # Initialize the Gemini model
    model_name = "gemini-2.0-flash"
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        print(f"Error: could not load Gemini model '{model_name}': {e}")
        return

    # Interactive CLI loop
    while True:
        try:
            query = input("\nEnter your search query (or 'exit' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query or query.lower() in ('exit', 'quit'):
            print("Goodbye!")
            break

        # 1) Ask Gemini: answer directly or route
        prompt = (
            f"You are a helpful assistant. The user asked:\n\"{query}\"\n\n"
            "— If you can answer this directly, just give the answer.\n"
            "— Otherwise reply exactly GOOGLE or YOUTUBE (no extra text)."
        )
        try:
            resp = model.generate_content(prompt)
            gemini_output = resp.text.strip()
        except Exception as e:
            print(f"Error: Gemini API call failed: {e}")
            gemini_output = ""

        # 2) Interpret Gemini's output
        decision = None
        answer   = None

        lower = gemini_output.lower()
        if lower == 'google':
            decision = 'GOOGLE'
        elif lower == 'youtube':
            decision = 'YOUTUBE'
        elif gemini_output:
            answer = gemini_output

        # 3) If Gemini gave an answer, show it
        if answer:
            print("\n💡 Gemini Answer:\n")
            print(answer)
            continue

        # 4) If Gemini routed to Google Videos
        if decision == 'GOOGLE':
            if not serpapi_api_key:
                print("Error: SERPAPI_API_KEY not set. Cannot perform Google video search.")
                continue
            try:
                from serpapi import GoogleSearch
            except ImportError:
                print("Error: install SerpAPI client: pip install google-search-results")
                continue

            print("\n🔎 Performing Google Videos search...")
            params = {
                "engine": "google_videos",
                "q": query,
                "api_key": serpapi_api_key,
            }
            try:
                results = GoogleSearch(params).get_dict().get('video_results', [])
            except Exception as e:
                print(f"Error: Google video search failed: {e}")
                continue

            if not results:
                print("No video results found on Google.")
            else:
                for i, vid in enumerate(results[:5], 1):
                    title = vid.get('title', '—')
                    link  = vid.get('link', '—')
                    desc  = vid.get('description', '')
                    print(f"{i}. {title}\n    {link}")
                    if desc:
                        print(f"    {desc}")
            continue

        # 5) If Gemini routed to YouTube
        if decision == 'YOUTUBE':
            # Try YouTube Data API first
            if youtube_api_key:
                try:
                    from googleapiclient.discovery import build
                except ImportError:
                    print("Error: install YouTube client: pip install google-api-python-client")
                else:
                    try:
                        yt = build("youtube", "v3", developerKey=youtube_api_key)
                        req = yt.search().list(
                            q=query, part="snippet", type="video", maxResults=5
                        )
                        items = req.execute().get("items", [])
                    except Exception as e:
                        print(f"Error: YouTube Data API failed: {e}")
                        items = []

                    if items:
                        print("\n▶️ YouTube Data API results:")
                        for i, it in enumerate(items, 1):
                            title = it["snippet"]["title"]
                            vidid = it["id"]["videoId"]
                            chan  = it["snippet"]["channelTitle"]
                            print(f"{i}. {title} (Channel: {chan}) — https://youtu.be/{vidid}")
                        continue
                    else:
                        print("YouTube Data API returned no results; falling back to SerpAPI.")

            # Fallback to SerpAPI YouTube search
            if not serpapi_api_key:
                print("Error: No API available for YouTube search (need YOUTUBE_API_KEY or SERPAPI_API_KEY).")
                continue
            try:
                from serpapi import GoogleSearch
            except ImportError:
                print("Error: install SerpAPI client: pip install google-search-results")
                continue

            print("\n🔎 Performing YouTube search via SerpAPI...")
            params = {
                "engine": "youtube",
                "search_query": query,
                "api_key": serpapi_api_key,
            }
            try:
                vids = GoogleSearch(params).get_dict().get("video_results", [])
            except Exception as e:
                print(f"Error: SerpAPI YouTube search failed: {e}")
                continue

            if not vids:
                print("No YouTube results found via SerpAPI.")
            else:
                print("\n▶️ YouTube SerpAPI results:")
                for i, vid in enumerate(vids[:5], 1):
                    title = vid.get("title", "—")
                    link  = vid.get("link", "—")
                    ch    = vid.get("channel", {}).get("name") or vid.get("channel_name", "—")
                    views = vid.get("views", "")
                    line = f"{i}. {title} — {link} (Channel: {ch})"
                    if views:
                        line += f" [{views}]"
                    print(line)
            continue

        # 6) If we get here, we have no route or answer
        print("⚠️ Unable to answer or determine search method. Please try rephrasing.")

if __name__ == "__main__":
    main()
