from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.collectors.base import BaseCollector

class LumaCollector(BaseCollector):
    """
    Collector for Lu.ma tech events and hackathons.
    Scrapes Lu.ma's discover/hackathon page.
    """
    
    def __init__(self):
        super().__init__("Lu.ma")
        # Lu.ma discovery endpoint with search queries for hackathons
        self.url = "https://lu.ma/discover?q=hackathon"

    def collect(self) -> List[Dict[str, Any]]:
        logger.info("Collecting hackathons from Lu.ma...")
        events = []
        
        response = self.fetch_url(self.url)
        if not response:
            logger.error("Could not fetch Lu.ma discover page.")
            return []
            
        try:
            soup = BeautifulSoup(response.text, "lxml")
            
            # Lu.ma lists event cards which contain event paths (e.g. lu.ma/xyz)
            # Find all anchors that match 'lu.ma/' and don't match static pages like '/discover'
            links = soup.select("a[href*='lu.ma/']")
            seen_urls = set()
            
            for link in links:
                url = link["href"]
                # Clean URL
                if "?" in url:
                    url = url.split("?")[0]
                    
                # Exclude non-event paths
                if any(x in url for x in ["/discover", "/create", "/login", "/home", "/about", "/pricing", "/faq"]):
                    continue
                    
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Try to resolve card parent to extract details
                card = link.parent.parent.parent # approximate card container
                
                title_tag = card.select_one("h1, h2, h3, .title, .event-name, [class*='title']")
                title = title_tag.text.strip() if title_tag else link.text.strip()
                if not title or len(title) < 5:
                    # skip garbage links
                    continue
                    
                # Date and location
                date_tag = card.select_one(".date, .time, [class*='date'], [class*='time']")
                date_str = date_tag.text.strip() if date_tag else None
                
                loc_tag = card.select_one(".location, .venue, [class*='location']")
                location = loc_tag.text.strip() if loc_tag else "Online"
                is_online = "online" in location.lower() or "zoom" in location.lower() or "virtual" in location.lower()
                
                # Lu.ma events are typically free unless specified
                prize_pool = "Lu.ma Networking / Learning"
                
                events.append({
                    "id": self.generate_hash(url),
                    "title": self.clean_string(title),
                    "url": url,
                    "platform": self.platform_name,
                    "hash": self.generate_hash(url),
                    "deadline": None,
                    "registration_open_date": None,
                    "image_url": None,
                    "prize_pool": prize_pool,
                    "location": location,
                    "is_online": is_online,
                    "country": None,
                    "theme": "Tech Event",
                    "organizer": "Lu.ma Organizer",
                    "participants_count": None,
                    "difficulty": "All levels",
                    "description": f"Lu.ma community tech event: {title}",
                    "tags": ["luma", "meetup", "hackathon"],
                    "team_required": False
                })
                
            logger.info(f"Successfully collected {len(events)} hackathons/events from Lu.ma.")
        except Exception as e:
            logger.error(f"Failed to scrape Lu.ma: {e}")
            
        return events
