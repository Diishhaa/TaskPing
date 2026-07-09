import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.collectors.base import BaseCollector

class DevpostCollector(BaseCollector):
    """
    Collector for Devpost hackathons. 
    Queries the Devpost JSON endpoint, with HTML parsing as a fallback.
    """
    
    def __init__(self):
        super().__init__("Devpost")
        self.api_url = "https://devpost.com/api/hackathons"
        self.html_url = "https://devpost.com/hackathons"

    def collect(self) -> List[Dict[str, Any]]:
        logger.info("Collecting hackathons from Devpost...")
        events = []
        
        # Try JSON API first
        response = self.fetch_url(self.api_url)
        if response:
            try:
                data = response.json()
                hackathons = data.get("hackathons", [])
                for h in hackathons:
                    url = h.get("url") or h.get("challenge_url")
                    if not url:
                        continue
                        
                    # Clean up URL (strip query parameters)
                    if "?" in url:
                        url = url.split("?")[0]
                        
                    title = h.get("title") or h.get("name")
                    if not title:
                        continue
                        
                    themes = h.get("themes") or h.get("tags") or []
                    if isinstance(themes, str):
                        themes = [t.strip() for t in themes.split(",") if t.strip()]
                        
                    # Deadlines parsing
                    deadline = h.get("submission_deadline") or h.get("deadline")
                    
                    is_online = h.get("is_online") or h.get("online", False)
                    location = h.get("location") or ("Online" if is_online else "In-Person")
                    if "online" in location.lower():
                        is_online = True
                        
                    events.append({
                        "id": self.generate_hash(url),
                        "title": self.clean_string(title),
                        "url": url,
                        "platform": self.platform_name,
                        "hash": self.generate_hash(url),
                        "deadline": deadline,
                        "registration_open_date": h.get("start_date"),
                        "image_url": h.get("thumbnail_url") or h.get("image"),
                        "prize_pool": h.get("prize_value") or h.get("prizes_total") or "0",
                        "location": location,
                        "is_online": is_online,
                        "country": h.get("country"),
                        "theme": ", ".join(themes[:3]),
                        "organizer": h.get("host") or h.get("organization") or "Devpost",
                        "participants_count": h.get("participants_count") or h.get("registrants_count"),
                        "difficulty": h.get("difficulty") or "All levels",
                        "description": h.get("description") or h.get("short_description") or "",
                        "tags": themes,
                        "team_required": h.get("team_required") or False
                    })
                
                if events:
                    logger.info(f"Successfully collected {len(events)} hackathons from Devpost API.")
                    return events
            except Exception as e:
                logger.warning(f"Failed to parse Devpost JSON API: {e}. Falling back to HTML scraping.")
                
        # HTML Scraping Fallback
        response = self.fetch_url(self.html_url)
        if not response:
            logger.error("Could not fetch Devpost HTML.")
            return []
            
        try:
            soup = BeautifulSoup(response.text, "lxml")
            # Devpost lists challenges in containers with class 'challenge-listing' or similar
            tiles = soup.select(".challenge-container, .hackathon-tile, .challenge-listing")
            
            for tile in tiles:
                link_tag = tile.select_one("a[href*='devpost.com'], a[href*='challenge']")
                if not link_tag:
                    continue
                url = link_tag["href"]
                if "?" in url:
                    url = url.split("?")[0]
                    
                title_tag = tile.select_one(".title, h3, h2")
                title = title_tag.text.strip() if title_tag else "Unnamed Hackathon"
                
                desc_tag = tile.select_one(".summary, .description, p")
                description = desc_tag.text.strip() if desc_tag else ""
                
                prize_tag = tile.select_one(".prize, .prize-value, .prize-pool")
                prize_pool = prize_tag.text.strip() if prize_tag else "0"
                
                deadline_tag = tile.select_one(".submission-deadline, .deadline, time")
                deadline = deadline_tag.text.strip() if deadline_tag else None
                
                participants_tag = tile.select_one(".participants, .registrants")
                participants = None
                if participants_tag:
                    try:
                        p_text = re.sub(r'\D', '', participants_tag.text)
                        participants = int(p_text) if p_text else None
                    except:
                        pass
                
                is_online = "online" in tile.text.lower() or "virtual" in tile.text.lower()
                location = "Online" if is_online else "In-Person"
                
                events.append({
                    "id": self.generate_hash(url),
                    "title": self.clean_string(title),
                    "url": url,
                    "platform": self.platform_name,
                    "hash": self.generate_hash(url),
                    "deadline": deadline,
                    "registration_open_date": None,
                    "image_url": None,
                    "prize_pool": prize_pool,
                    "location": location,
                    "is_online": is_online,
                    "country": None,
                    "theme": "",
                    "organizer": "Devpost",
                    "participants_count": participants,
                    "difficulty": "All levels",
                    "description": description,
                    "tags": [],
                    "team_required": False
                })
                
            logger.info(f"Successfully collected {len(events)} hackathons from Devpost HTML.")
        except Exception as e:
            logger.error(f"Failed to parse Devpost HTML: {e}")
            
        return events
