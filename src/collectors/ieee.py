from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.collectors.base import BaseCollector

class IeeeCollector(BaseCollector):
    """
    Collector for IEEE competitions and student hackathons.
    Scrapes the IEEE Student Competitions portal.
    """
    
    def __init__(self):
        super().__init__("IEEE")
        self.url = "https://www.ieee.org/education/student-competitions.html"

    def collect(self) -> List[Dict[str, Any]]:
        logger.info("Collecting hackathons from IEEE...")
        events = []
        
        response = self.fetch_url(self.url)
        if not response:
            logger.error("Could not fetch IEEE Competitions page.")
            return []
            
        try:
            soup = BeautifulSoup(response.text, "lxml")
            
            # Look for list items or divs that contain external links
            # IEEE page has competition details in paragraph tags or list items under specific headings
            content_area = soup.select_one(".middle-column, #main-content, .ieee-content") or soup
            links = content_area.select("a[href*='ieee.org'], a[href*='ieeextreme']")
            
            seen_urls = set()
            for link in links:
                url = link["href"]
                if "?" in url:
                    url = url.split("?")[0]
                    
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                title = link.text.strip()
                if not title or len(title) < 5 or any(x in title.lower() for x in ["read more", "click here", "details", "contact"]):
                    continue
                    
                # IEEE Extreme is the most popular IEEE competition, check for it
                is_extreme = "extreme" in url.lower() or "ieeextreme" in title.lower()
                prize_pool = "IEEE Travel Grants / Cash Prizes" if is_extreme else "Certificates & Publications"
                location = "Online / Global Chapters" if is_extreme else "IEEE Sections"
                is_online = True
                
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
                    "country": "Global",
                    "theme": "Student Competition",
                    "organizer": "IEEE",
                    "participants_count": None,
                    "difficulty": "All levels",
                    "description": f"IEEE sponsored academic/engineering competition: {title}",
                    "tags": ["ieee", "student", "engineering", "competition"],
                    "team_required": True if is_extreme else False
                })
                
            # Default fallback if no specific links found
            if not events:
                url = "https://ieeextreme.org/"
                events.append({
                    "id": self.generate_hash(url),
                    "title": "IEEEXtreme 24-Hour Programming Competition",
                    "url": url,
                    "platform": self.platform_name,
                    "hash": self.generate_hash(url),
                    "deadline": None,
                    "registration_open_date": None,
                    "image_url": None,
                    "prize_pool": "Fully funded trip to IEEE conference",
                    "location": "Online / IEEE Student Branches",
                    "is_online": True,
                    "country": "Global",
                    "theme": "Coding Competition",
                    "organizer": "IEEE",
                    "participants_count": 10000,
                    "difficulty": "Hard",
                    "description": "IEEEXtreme is a global virtual hackathon in which teams of IEEE student members compete in a 24-hour time span to solve a set of programming problems.",
                    "tags": ["ieee", "ieeextreme", "programming", "contest"],
                    "team_required": True
                })
                
            logger.info(f"Successfully collected {len(events)} hackathons/competitions from IEEE.")
        except Exception as e:
            logger.error(f"Failed to scrape IEEE: {e}")
            
        return events
