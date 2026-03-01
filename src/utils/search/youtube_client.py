import re
from youtube_transcript_api import YouTubeTranscriptApi
from src.utils.console import colored
from typing import List, Dict
from .base import BaseSearchClient
from ddgs import DDGS

class YouTubeClient(BaseSearchClient):
    def search(self, query: str, limit: int = 3) -> List[Dict[str, str]]:
        # Transcripts are long, so limit is defaulted lower than standard search
        print(colored(f"[Search: YouTube] Searching for videos about '{query}'...", "cyan"))
        results = []
        try:
            # 1. Ask DDG for YouTube links for the query
            dorked_query = f'site:youtube.com {query}'
            video_ids = []
            with DDGS() as ddgs:
                search_results = ddgs.text(dorked_query, max_results=limit * 2)
            
            if search_results:
                for r in search_results:
                    url = r.get('href', '')
                    # 2. Extract YouTube Video ID from standard YouTube URL patterns
                    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
                    if match:
                        vid = match.group(1)
                        if vid not in [v['id'] for v in video_ids]:
                            video_ids.append({'id': vid, 'title': r.get('title', ''), 'url': url})
                    if len(video_ids) >= limit:
                        break
            
            # 3. Pull transcripts
            for vid_obj in video_ids:
                try:
                    transcript_list = YouTubeTranscriptApi.get_transcript(vid_obj['id'])
                    # Join text
                    full_text = " ".join([t['text'] for t in transcript_list])
                    # Truncate to ~3000 chars so we don't blow up LLM context with a 2-hour podcast transcript.
                    truncated_text = full_text[:3000] + ("..." if len(full_text) > 3000 else "")
                    
                    results.append({
                        "title": vid_obj['title'],
                        "text": truncated_text,
                        "url": vid_obj['url'],
                        "source": "YouTube Transcript"
                    })
                except Exception:
                    # Transcript disabled or auto-gen not available
                    continue
                    
        except Exception as e:
            print(colored(f"[Search: YouTube] Error fetching data: {e}", "red"))
            
        return results
