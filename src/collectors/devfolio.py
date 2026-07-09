import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.collectors.base import BaseCollector

class DevfolioCollector(BaseCollector):
    """
    Collector for Devfolio hackathons.
    Tries Devfolio's API, Next.js props parsing, and HTML scraping as fallbacks.
    """
    
    def __init__(self):
        super().__init__("Devfolio")
        self.api_url = "https://api.devfolio.co/api/hackathons"
        self.html_url = "https://devfolio.co/hackathons"

    def _parse_themes(self, h: Dict[str, Any]) -> List[str]:
        themes = h.get("themes") or h.get("tags") or []
        if isinstance(themes, str):
            return [t.strip() for t in themes.split(",") if t.strip()]
        
        parsed = []
        if isinstance(themes, list):
            for t in themes:
                if isinstance(t, dict):
                    name = t.get("name") or t.get("slug")
                    if name:
                        parsed.append(str(name))
                elif t:
                    parsed.append(str(t))
        return parsed

    def collect(self) -> List[Dict[str, Any]]:
        logger.info("Collecting hackathons from Devfolio...")
        events = []
        
        # Try JSON API
        # Devfolio API often requires POST with filter criteria, or GET
        for method in ["POST", "GET"]:
            payload = {"type": "open"} if method == "POST" else None
            response = self.fetch_url(self.api_url, method=method, json_data=payload)
            if response:
                try:
                    data = response.json()
                    # Devfolio returns list directly or under 'hackathons' or 'results'
                    hackathons = data if isinstance(data, list) else data.get("hackathons") or data.get("results") or []
                    
                    for h in hackathons:
                        url = h.get("url") or h.get("hackathon_url") or h.get("site_url")
                        slug = h.get("slug")
                        if not url and slug:
                            url = f"https://{slug}.devfolio.co"
                        if not url:
                            continue
                            
                        title = h.get("name") or h.get("title")
                        if not title:
                            continue
                            
                        # Extract dates
                        deadline = h.get("submissions_close") or h.get("ends_at") or h.get("end_date")
                        open_date = h.get("submissions_open") or h.get("starts_at") or h.get("start_date")
                        
                        # Prize
                        prize_pool = h.get("prize_money") or h.get("prizes_total") or "0"
                        
                        # Online / Offline
                        is_online = h.get("is_online") or h.get("online", False)
                        venue = h.get("venue") or h.get("location") or ""
                        if "online" in venue.lower() or "virtual" in venue.lower():
                            is_online = True
                            venue = "Online"
                        elif not venue:
                            venue = "Online" if is_online else "In-Person"
                            
                        tags = self._parse_themes(h)
                            
                        events.append({
                            "id": self.generate_hash(url),
                            "title": self.clean_string(title),
                            "url": url,
                            "platform": self.platform_name,
                            "hash": self.generate_hash(url),
                            "deadline": deadline,
                            "registration_open_date": open_date,
                            "image_url": h.get("logo") or h.get("image_url") or h.get("banner"),
                            "prize_pool": str(prize_pool),
                            "location": venue,
                            "is_online": is_online,
                            "country": h.get("country"),
                            "theme": ", ".join(tags[:3]),
                            "organizer": h.get("organizer", {}).get("name") if isinstance(h.get("organizer"), dict) else "Devfolio",
                            "participants_count": h.get("participants_count") or h.get("registrations_count"),
                            "difficulty": "All levels",
                            "description": h.get("tagline") or h.get("description") or "",
                            "tags": tags,
                            "team_required": h.get("team_required") or False
                        })
                    
                    if events:
                        logger.info(f"Successfully collected {len(events)} hackathons from Devfolio API.")
                        return events
                except Exception as e:
                    logger.debug(f"Devfolio API {method} parse failed: {e}")
                    
        # Try Next.js __NEXT_DATA__ HTML parsing fallback
        response = self.fetch_url(self.html_url)
        if not response:
            logger.error("Could not fetch Devfolio HTML.")
            return []
            
        try:
            soup = BeautifulSoup(response.text, "lxml")
            script_tag = soup.find("script", id="__NEXT_DATA__")
            if script_tag:
                next_data = json.loads(script_tag.string)
                # Query props recursively
                opportunities = self._find_hackathons_recursive(next_data)
                
                for h in opportunities:
                    slug = h.get("slug")
                    if not slug:
                        continue
                    url = f"https://{slug}.devfolio.co"
                    title = h.get("name")
                    if not title:
                        continue
                        
                    deadline = h.get("ends_at") or h.get("submissions_close")
                    open_date = h.get("starts_at") or h.get("submissions_open")
                    
                    # Prize
                    prizes = h.get("prizes") or []
                    prize_pool = "0"
                    if isinstance(prizes, list) and prizes:
                        prize_pool = str(prizes[0])
                    
                    is_online = h.get("is_online") or False
                    location = "Online" if is_online else "In-Person"
                    
                    tags = self._parse_themes(h)
                    
                    events.append({
                        "id": self.generate_hash(url),
                        "title": self.clean_string(title),
                        "url": url,
                        "platform": self.platform_name,
                        "hash": self.generate_hash(url),
                        "deadline": deadline,
                        "registration_open_date": open_date,
                        "image_url": h.get("logo") or h.get("hero_image"),
                        "prize_pool": prize_pool,
                        "location": location,
                        "is_online": is_online,
                        "country": None,
                        "theme": ", ".join(tags[:3]),
                        "organizer": "Devfolio",
                        "participants_count": h.get("participants_count"),
                        "difficulty": "All levels",
                        "description": h.get("tagline") or "",
                        "tags": tags,
                        "team_required": False
                    })
                
                if events:
                    logger.info(f"Successfully collected {len(events)} hackathons from Devfolio Next.js props.")
                    return events
        except Exception as e:
            logger.warning(f"Failed to parse Devfolio Next.js props: {e}")
            
        # HTML Scraping Fallback (BeautifulSoup parsing)
        try:
            soup = BeautifulSoup(response.text, "lxml")
            cards = soup.select("[class*='HackathonCard'], [class*='Card'], .hackathon-card")
            for card in cards:
                link = card.select_one("a[href*='devfolio.co']")
                if not link:
                    continue
                url = link["href"]
                
                title_tag = card.select_one("h3, h2, .title, [class*='name']")
                title = title_tag.text.strip() if title_tag else "Unnamed Devfolio Hackathon"
                
                prize_tag = card.select_one("[class*='prize'], .prize, .rewards")
                prize = prize_tag.text.strip() if prize_tag else "0"
                
                events.append({
                    "id": self.generate_hash(url),
                    "title": self.clean_string(title),
                    "url": url,
                    "platform": self.platform_name,
                    "hash": self.generate_hash(url),
                    "deadline": None,
                    "registration_open_date": None,
                    "image_url": None,
                    "prize_pool": prize,
                    "location": "Online",
                    "is_online": True,
                    "country": None,
                    "theme": "",
                    "organizer": "Devfolio",
                    "participants_count": None,
                    "difficulty": "All levels",
                    "description": "",
                    "tags": [],
                    "team_required": False
                })
                
            logger.info(f"Fallback scraper fetched {len(events)} hackathons from Devfolio HTML.")
        except Exception as e:
            logger.error(f"Devfolio HTML scrape failed: {e}")
            
        return events

    def _find_hackathons_recursive(self, data: Any) -> List[Dict[str, Any]]:
        """Recursively parses a dictionary/list to find a list of hackathon-like items."""
        if isinstance(data, list):
            if data and isinstance(data[0], dict) and "slug" in data[0] and "name" in data[0] and "starts_at" in data[0]:
                return data
            for item in data:
                res = self._find_hackathons_recursive(item)
                if res:
                    return res
        elif isinstance(data, dict):
            for key in ["hackathons", "results", "data", "open_hackathons", "active_hackathons"]:
                if key in data:
                    res = self._find_hackathons_recursive(data[key])
                    if res:
                        return res
            for k, v in data.items():
                if k not in ["hackathons", "results", "data", "open_hackathons", "active_hackathons"]:
                    res = self._find_hackathons_recursive(v)
                    if res:
                        return res
        return []
