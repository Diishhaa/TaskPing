from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.collectors.base import BaseCollector

class MicrosoftCollector(BaseCollector):
    """
    Collector for Microsoft Developer Events.
    Scrapes the Microsoft Developer events portal.
    """
    
    def __init__(self):
        super().__init__("Microsoft")
        self.url = "https://developer.microsoft.com/en-us/events"

    def collect(self) -> List[Dict[str, Any]]:
        logger.info("Collecting hackathons from Microsoft Developer Events...")
        events = []
        
        response = self.fetch_url(self.url)
        if not response:
            logger.error("Could not fetch Microsoft Developer Events page.")
            return []
            
        try:
            soup = BeautifulSoup(response.text, "lxml")
            
            # Extract cards
            cards = soup.select(".card, [class*='card'], .event-item, .ms-card")
            for card in cards:
                link = card.select_one("a[href*='microsoft.com']")
                if not link:
                    continue
                url = link["href"]
                
                title_tag = card.select_one("h3, h4, .title, [class*='title']")
                title = title_tag.text.strip() if title_tag else link.text.strip()
                
                desc_tag = card.select_one(".description, .summary, p")
                description = desc_tag.text.strip() if desc_tag else ""
                
                date_tag = card.select_one(".date, .time, [class*='date']")
                date_str = date_tag.text.strip() if date_tag else None
                
                location = "Online"
                is_online = True
                loc_tag = card.select_one(".location, .venue, [class*='location']")
                if loc_tag:
                    location = loc_tag.text.strip()
                    is_online = "online" in location.lower() or "virtual" in location.lower()
                    
                events.append({
                    "id": self.generate_hash(url),
                    "title": self.clean_string(title),
                    "url": url,
                    "platform": self.platform_name,
                    "hash": self.generate_hash(url),
                    "deadline": None,
                    "registration_open_date": None,
                    "image_url": None,
                    "prize_pool": "Azure Credits & Microsoft Swag",
                    "location": location,
                    "is_online": is_online,
                    "country": None,
                    "theme": "Microsoft Developer Event",
                    "organizer": "Microsoft",
                    "participants_count": None,
                    "difficulty": "All levels",
                    "description": self.clean_string(description),
                    "tags": ["microsoft", "azure", "ai", "copilot"],
                    "team_required": False
                })
                
            # Fallback default link if scraping did not return any items
            if not events:
                url = "https://events.microsoft.com/"
                events.append({
                    "id": self.generate_hash(url),
                    "title": "Microsoft AI Hackathons & Developer Events",
                    "url": url,
                    "platform": self.platform_name,
                    "hash": self.generate_hash(url),
                    "deadline": None,
                    "registration_open_date": None,
                    "image_url": None,
                    "prize_pool": "Azure Credits",
                    "location": "Global / Online",
                    "is_online": True,
                    "country": "Global",
                    "theme": "Azure / Copilot AI",
                    "organizer": "Microsoft Developer Relations",
                    "participants_count": None,
                    "difficulty": "All levels",
                    "description": "Microsoft-sponsored developer events, virtual training days, and AI hackathons.",
                    "tags": ["microsoft", "azure", "ai", "hackathon"],
                    "team_required": False
                })
                
            logger.info(f"Successfully collected {len(events)} hackathons/events from Microsoft.")
        except Exception as e:
            logger.error(f"Failed to scrape Microsoft Events: {e}")
            
        return events
