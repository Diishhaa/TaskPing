import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.collectors.base import BaseCollector

class UnstopCollector(BaseCollector):
    """
    Collector for Unstop hackathons.
    Extracts Next.js __NEXT_DATA__ JSON from the HTML page for structured data access.
    """
    
    def __init__(self):
        super().__init__("Unstop")
        self.url = "https://unstop.com/hackathons"

    def collect(self) -> List[Dict[str, Any]]:
        logger.info("Collecting hackathons from Unstop...")
        events = []
        
        response = self.fetch_url(self.url)
        if not response:
            logger.error("Could not fetch Unstop HTML.")
            return []
            
        try:
            soup = BeautifulSoup(response.text, "lxml")
            script_tag = soup.find("script", id="__NEXT_DATA__")
            
            if not script_tag:
                logger.warning("Could not find __NEXT_DATA__ script tag on Unstop. Scraping HTML cards instead.")
                return self._scrape_cards_fallback(soup)
                
            next_data = json.loads(script_tag.string)
            
            # Navigate nested Next.js props structure to find hackathons
            # Different pages might have different data paths, so let's use a safe recursive lookup
            opportunities = self._find_opportunities(next_data)
            
            if not opportunities:
                logger.warning("No opportunities found in __NEXT_DATA__. Scraping HTML cards instead.")
                return self._scrape_cards_fallback(soup)
                
            for opp in opportunities:
                # Opportunity URLs on Unstop are usually like: https://unstop.com/o/slug
                slug = opp.get("public_url") or opp.get("slug")
                if not slug:
                    continue
                
                url = f"https://unstop.com/o/{slug}" if not slug.startswith("http") else slug
                
                title = opp.get("title") or opp.get("name")
                if not title:
                    continue
                
                # Registration and Deadlines
                # End date is usually reg_end_date or end_date or similar
                deadline = opp.get("reg_end_date") or opp.get("end_date") or opp.get("deadline")
                open_date = opp.get("reg_start_date") or opp.get("start_date")
                
                # Image and Prize
                image_url = opp.get("banner_image") or opp.get("logoUrl") or opp.get("logo_url")
                
                prizes = opp.get("prizes") or []
                prize_pool = "INR 0"
                if isinstance(prizes, list) and prizes:
                    # Look for cash prizes
                    cash_prizes = [p.get("cash_prize") or p.get("prize_value") for p in prizes if p.get("cash_prize") or p.get("prize_value")]
                    if cash_prizes:
                        prize_pool = f"INR {sum(int(re.sub(r'\D', '', str(cp))) for cp in cash_prizes if str(cp).isdigit())}"
                elif opp.get("prize_money") or opp.get("prize_pool"):
                    prize_pool = str(opp.get("prize_money") or opp.get("prize_pool"))
                
                # Location and Online
                is_online = opp.get("is_online") or False
                venue = opp.get("venue") or opp.get("location") or ""
                if "online" in venue.lower() or "virtual" in venue.lower() or opp.get("is_virtual"):
                    is_online = True
                    venue = "Online"
                elif not venue:
                    venue = "Online" if is_online else "In-Person"
                    
                # Tags
                tags = []
                for key in ["filters", "tags", "categories", "eligible"]:
                    vals = opp.get(key)
                    if isinstance(vals, list):
                        tags.extend([str(v) for v in vals if v])
                    elif isinstance(vals, str):
                        tags.append(vals)
                
                organizer = "Unstop"
                org_obj = opp.get("organisation") or opp.get("organizer")
                if org_obj and isinstance(org_obj, dict):
                    organizer = org_obj.get("name") or organizer
                
                desc = opp.get("brief_intro") or opp.get("description") or ""
                
                events.append({
                    "id": self.generate_hash(url),
                    "title": self.clean_string(title),
                    "url": url,
                    "platform": self.platform_name,
                    "hash": self.generate_hash(url),
                    "deadline": deadline,
                    "registration_open_date": open_date,
                    "image_url": image_url,
                    "prize_pool": prize_pool,
                    "location": venue,
                    "is_online": is_online,
                    "country": opp.get("country") or "India",
                    "theme": ", ".join(tags[:3]),
                    "organizer": organizer,
                    "participants_count": opp.get("participants_count") or opp.get("reg_count") or opp.get("registered_count"),
                    "difficulty": "All levels",
                    "description": self.clean_string(desc),
                    "tags": list(set(tags)),
                    "team_required": opp.get("team_required") or False
                })
                
            logger.info(f"Successfully collected {len(events)} hackathons from Unstop JSON.")
        except Exception as e:
            logger.error(f"Failed to parse Unstop __NEXT_DATA__: {e}")
            
        return events

    def _find_opportunities(self, data: Any) -> List[Dict[str, Any]]:
        """Recursively searches the Next.js props for any opportunity list."""
        if isinstance(data, list):
            # Check if this list contains opportunity-like dictionaries
            if data and isinstance(data[0], dict) and ("public_url" in data[0] or "slug" in data[0]) and ("title" in data[0] or "name" in data[0]):
                return data
            for item in data:
                res = self._find_opportunities(item)
                if res:
                    return res
        elif isinstance(data, dict):
            # Check common keys
            for key in ["opportunities", "opportunity", "data", "list", "results"]:
                if key in data:
                    res = self._find_opportunities(data[key])
                    if res:
                        return res
            for k, v in data.items():
                if k not in ["opportunities", "opportunity", "data", "list", "results"]:
                    res = self._find_opportunities(v)
                    if res:
                        return res
        return []

    def _scrape_cards_fallback(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """BeautifulSoup fallback scraper for Unstop if __NEXT_DATA__ fails."""
        events = []
        # Unstop hackathon cards typically have class containing 'opportunity-card' or 'listing'
        cards = soup.select(".opportunity_card, .listing-card, .competitions-card, [class*='card']")
        
        for card in cards:
            link = card.select_one("a[href*='/o/'], a[href*='unstop.com/o/']")
            if not link:
                continue
            
            url = link["href"]
            if not url.startswith("http"):
                url = f"https://unstop.com{url}"
                
            title_tag = card.select_one(".title, .heading, h3, h2, [class*='title']")
            title = title_tag.text.strip() if title_tag else "Unnamed Unstop Hackathon"
            
            prize_tag = card.select_one(".prize, .rewards, .cash, [class*='prize']")
            prize = prize_tag.text.strip() if prize_tag else "0"
            
            deadline_tag = card.select_one(".deadline, .date, [class*='date'], [class*='deadline']")
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
                "organizer": "Unstop",
                "participants_count": None,
                "difficulty": "All levels",
                "description": "",
                "tags": [],
                "team_required": False
            })
            
        logger.info(f"Fallback scraper fetched {len(events)} hackathons from Unstop HTML.")
        return events
