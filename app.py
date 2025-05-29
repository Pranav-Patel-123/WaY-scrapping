#!/usr/bin/env python3
# app.py — FastAPI wrapper around Gemini, YouTube Data API, and SerpAPI

import os
from typing import List, Optional, Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Environment variables
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY")
YOUTUBE_API_KEY  = os.getenv("YOUTUBE_API_KEY")
SERPAPI_API_KEY  = os.getenv("SERPAPI_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY must be set in environment")

# Configure Gemini SDK
import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.0-flash"
try:
    GEMINI_MODEL = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    raise RuntimeError(f"Failed to load Gemini model '{MODEL_NAME}': {e}")

# FastAPI app
app = FastAPI(title="Search Assistant API")

# Allow all origins (adjust in production!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

# Pydantic models
class QueryRequest(BaseModel):
    query: str

class VideoResult(BaseModel):
    title: str
    link: str
    description: Optional[str] = None
    channel: Optional[str] = None
    views: Optional[str] = None

class SearchResponse(BaseModel):
    source: Literal["gemini", "google_videos", "youtube"]
    answer: Optional[str] = None
    results: Optional[List[VideoResult]] = None

# Helper: ask Gemini
def ask_gemini(query: str) -> str:
    prompt = (
        f"You are a helpful assistant. The user asked:\n\"{query}\"\n\n"
        "— If you can answer this directly, just give the answer.\n"
        "— Otherwise reply exactly GOOGLE or YOUTUBE (no extra text)."
    )
    resp = GEMINI_MODEL.generate_content(prompt)
    return resp.text.strip()

# Endpoint
@app.post("/search", response_model=SearchResponse)
def search(req: QueryRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    # 1) Ask Gemini
    try:
        gemini_out = ask_gemini(query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {e}")

    lower = gemini_out.lower()
    # Direct answer
    if gemini_out and lower not in ("google", "youtube"):
        return SearchResponse(source="gemini", answer=gemini_out)

    # Google Videos
    if lower == "google":
        if not SERPAPI_API_KEY:
            raise HTTPException(status_code=500, detail="SERPAPI_API_KEY not set")

        from serpapi import GoogleSearch
        params = {
            "engine": "google_videos",
            "q": query,
            "api_key": SERPAPI_API_KEY,
        }
        try:
            data = GoogleSearch(params).get_dict()
            vids = data.get("video_results", [])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"SerpAPI error: {e}")

        results = [
            VideoResult(
                title=v.get("title", ""),
                link=v.get("link", ""),
                description=v.get("description"),
                channel=v.get("channel", {}).get("name") or v.get("channel_name"),
                views=v.get("views"),
            )
            for v in vids[:5]
        ]
        return SearchResponse(source="google_videos", results=results)

    # YouTube
    if lower == "youtube":
        items = []
        # Try YouTube Data API
        if YOUTUBE_API_KEY:
            try:
                from googleapiclient.discovery import build
                yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
                resp = yt.search().list(
                    q=query, part="snippet", type="video", maxResults=5
                ).execute()
                items = resp.get("items", [])
            except Exception:
                items = []

        # Fallback to SerpAPI if needed
        if not items:
            if not SERPAPI_API_KEY:
                raise HTTPException(status_code=500, detail="No YouTube search API key available")
            from serpapi import GoogleSearch
            params = {
                "engine": "youtube",
                "search_query": query,
                "api_key": SERPAPI_API_KEY,
            }
            try:
                data = GoogleSearch(params).get_dict()
                items = data.get("video_results", [])
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"SerpAPI YouTube error: {e}")

            # Format SerpAPI YouTube schema
            results = [
                VideoResult(
                    title=i.get("title", ""),
                    link=i.get("link", ""),
                    channel=i.get("channel", {}).get("name") or i.get("channel_name"),
                    views=i.get("views"),
                )
                for i in items[:5]
            ]
        else:
            # Format YouTube Data API schema
            results = [
                VideoResult(
                    title=i["snippet"]["title"],
                    link=f"https://youtu.be/{i['id']['videoId']}",
                    channel=i["snippet"]["channelTitle"],
                )
                for i in items
            ]

        return SearchResponse(source="youtube", results=results)

    # Fallback
    raise HTTPException(status_code=422, detail="Unable to determine search method; try rephrasing")

# Healthcheck
@app.get("/")
def root():
    return {"status": "ok", "message": "Search Assistant API is running"}
