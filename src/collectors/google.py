from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.collectors.base import BaseCollector

class GoogleCollector(BaseCollector):
    """
    Collector for Google Developer Events (Gemini Hackathons, Build with AI, etc.)
    Scrapes the Google Developers event page.
    """
    
    def __init__(self):
        super().__init__("Google")
        self.url = "https://developers.google.com/events"

    def collect(self) -> List[Dict[str, Any]]:
        logger.info("Collecting hackathons from Google Developer Events...")
        events = []
        
        response = self.fetch_url(self.url)
        if not response:
            logger.error("Could not fetch Google Developer Events page.")
            return []
            
        try:
            soup = BeautifulSoup(response.text, "lxml")
            
            # Google Events page cards have tags or attributes describing event details
            # Common structures: divs containing class devsite-card or event cards
            cards = soup.select(".devsite-card, .event-card, .card, [class*='card']")
            
            for card in cards:
                link = card.select_one("a[href*='developers.google.com'], a[href*='gdg.community.dev']")
                if not link:
                    continue
                url = link["href"]
                
                title_tag = card.select_one("h3, h4, .title, [class*='title']")
                title = title_tag.text.strip() if title_tag else link.text.strip()
                
                # We specifically look for AI, Gemini, Build with AI, or ML related events
                # if the listing page contains other Google events (like Android, Flutter, Web)
                # We want to make sure it's relevant, or collect all developer events
                
                desc_tag = card.select_one(".description, .summary, p")
                description = desc_tag.text.strip() if desc_tag else ""
                
                date_tag = card.select_one(".date, .time, [class*='date']")
                date_str = date_tag.text.strip() if date_tag else None
                
                # Check for location
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
                    "prize_pool": "Google Swag & Cloud Credits",
                    "location": location,
                    "is_online": is_online,
                    "country": None,
                    "theme": "Google Developer Event",
                    "organizer": "Google Developers",
                    "participants_count": None,
                    "difficulty": "All levels",
                    "description": self.clean_string(description),
                    "tags": ["google", "gemini", "buildwithai", "gdg"],
                    "team_required": False
                })
                
            # Fallback if no cards were found: add a mock event to keep Google platform visible or just log
            if not events:
                logger.warning("No dynamic cards found on Google Developers page, adding default community link.")
                # We can add the general search URL as a reference
                url = "https://gdg.community.dev/?q=Build%20with%20AI"
                events.append({
                    "id": self.generate_hash(url),
                    "title": "Google Build with AI / Gemini Hackathons",
                    "url": url,
                    "platform": self.platform_name,
                    "hash": self.generate_hash(url),
                    "deadline": None,
                    "registration_open_date": None,
                    "image_url": None,
                    "prize_pool": "Varies by location",
                    "location": "Global GDG Chapters",
                    "is_online": True,
                    "country": "Global",
                    "theme": "Artificial Intelligence",
                    "organizer": "Google Developer Groups",
                    "participants_count": None,
                    "difficulty": "All levels",
                    "description": "Find community-led hackathons and workshops focused on Google Gemini, Gemma, and Vertex AI.",
                    "tags": ["google", "gemini", "ai", "gdg"],
                    "team_required": False
                })
                
            logger.info(f"Successfully collected {len(events)} hackathons/events from Google Developers.")
        except Exception as e:
            logger.error(f"Failed to scrape Google Events: {e}")
            
        return events
