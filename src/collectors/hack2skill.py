import re
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.collectors.base import BaseCollector

class Hack2SkillCollector(BaseCollector):
    """
    Collector for Hack2Skill hackathons.
    Scrapes the Hack2Skill opportunities list and extracts event details.
    """
    
    def __init__(self):
        super().__init__("Hack2Skill")
        self.url = "https://hack2skill.com/opportunities/hackathons"
        self.fallback_url = "https://hack2skill.com"

    def collect(self) -> List[Dict[str, Any]]:
        logger.info("Collecting hackathons from Hack2Skill...")
        events = []
        
        # Try primary opportunities list
        response = self.fetch_url(self.url)
        if not response:
            logger.warning("Could not fetch Hack2Skill opportunities page, trying landing page fallback.")
            response = self.fetch_url(self.fallback_url)
            
        if not response:
            logger.error("Could not fetch Hack2Skill website.")
            return []
            
        try:
            soup = BeautifulSoup(response.text, "lxml")
            
            # Hack2Skill cards typically have anchors to event subdomains or '/event/' path
            # We look for all links containing 'event/' or on hack2skill subdomains
            cards = soup.select(".card, [class*='card'], .opportunity-card, [class*='event']")
            
            # If no structured cards are found, scan all links in the page to find event URLs
            links = []
            if cards:
                for card in cards:
                    a_tags = card.select("a[href*='hack2skill.com/event/'], a[href*='hack2skill.com/opportunities/'], a[href*='.hack2skill.com']")
                    for a in a_tags:
                        links.append((a, card))
            
            # If still nothing, search all anchors in the page
            if not links:
                for a in soup.select("a[href*='hack2skill.com/event/'], a[href*='hack2skill.com/opportunities/']"):
                    links.append((a, a.parent.parent)) # approximate card parent
            
            seen_urls = set()
            for a, card in links:
                url = a["href"]
                if "?" in url:
                    url = url.split("?")[0]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Title
                # Find title text inside the card or link itself
                title_tag = card.select_one("h3, h4, h2, .title, .heading, [class*='title']")
                title = title_tag.text.strip() if title_tag else a.text.strip()
                if not title or len(title) < 3:
                    title = "Hack2Skill Hackathon"
                    
                # Prize
                prize_tag = card.select_one("[class*='prize'], [class*='reward'], .prize, .rewards")
                prize = prize_tag.text.strip() if prize_tag else "INR 0"
                
                # Deadline/Date
                deadline_tag = card.select_one("[class*='date'], [class*='deadline'], .date, .deadline")
                deadline = deadline_tag.text.strip() if deadline_tag else None
                
                is_online = "online" in card.text.lower() or "virtual" in card.text.lower()
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
                    "prize_pool": prize,
                    "location": location,
                    "is_online": is_online,
                    "country": "India",
                    "theme": "",
                    "organizer": "Hack2Skill",
                    "participants_count": None,
                    "difficulty": "All levels",
                    "description": "",
                    "tags": ["hack2skill"],
                    "team_required": False
                })
                
            logger.info(f"Successfully collected {len(events)} hackathons from Hack2Skill.")
        except Exception as e:
            logger.error(f"Failed to scrape Hack2Skill: {e}")
            
        return events
