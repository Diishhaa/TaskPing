import re
from datetime import datetime, timezone
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.collectors.base import BaseCollector

class MlhCollector(BaseCollector):
    """
    Collector for Major League Hacking (MLH) events.
    Fetches the static HTML page of the current MLH season events and scrapes it.
    """
    
    def __init__(self):
        super().__init__("MLH")
        # MLH seasons correspond to academic years or calendar years
        # Let's dynamically determine current and next season
        now = datetime.now()
        self.seasons = [str(now.year), str(now.year + 1)]

    def collect(self) -> List[Dict[str, Any]]:
        logger.info("Collecting hackathons from MLH...")
        events = []
        
        for season in self.seasons:
            url = f"https://mlh.io/seasons/{season}/events"
            logger.info(f"Fetching MLH season {season} events from: {url}")
            
            response = self.fetch_url(url)
            if not response:
                logger.warning(f"Could not fetch MLH events for season {season}.")
                continue
                
            try:
                soup = BeautifulSoup(response.text, "lxml")
                
                # MLH event cards are typically contained in divs with classes like 'event-card' or 'event'
                cards = soup.select(".event-card-link, a[href*='mlh.io/events/'], .event")
                
                for card in cards:
                    # Get the link
                    url_val = card.get("href")
                    if not url_val:
                        link_tag = card.select_one("a")
                        url_val = link_tag["href"] if link_tag else None
                        
                    if not url_val:
                        continue
                        
                    if not url_val.startswith("http"):
                        url_val = f"https://mlh.io{url_val}"
                        
                    # Title
                    title_tag = card.select_one(".event-name, h3, h2, [itemprop='name']")
                    title = title_tag.text.strip() if title_tag else "MLH Hackathon"
                    
                    # Date
                    date_tag = card.select_one(".event-date, [itemprop='startDate']")
                    date_str = date_tag.text.strip() if date_tag else ""
                    
                    # Parse deadline and start date from text
                    # Example: "October 13-15" or "Oct 13, 2026"
                    deadline_iso = None
                    start_iso = None
                    if date_str:
                        # Clean date string
                        date_str = self.clean_string(date_str)
                        try:
                            # Let's check if the date includes a year, if not append season year
                            parse_str = date_str
                            if not any(char.isdigit() for char in date_str.split()[-1]):
                                # If the last token is not a digit, append season
                                parse_str = f"{date_str}, {season}"
                                
                            # Convert to ISO format (start date)
                            # E.g. "Oct 13-15, 2026" -> Start date is Oct 13, 2026
                            # We can use a regex to extract start date
                            match = re.match(r"([A-Za-z]+)\s+(\d+)", parse_str)
                            if match:
                                month, day = match.groups()
                                start_iso = datetime.strptime(f"{month} {day} {season}", "%b %d %Y").replace(tzinfo=timezone.utc).isoformat()
                                # Deadline is usually the last day of the event
                                # E.g. "Oct 13-15, 2026" -> End date is Oct 15, 2026
                                end_day_match = re.search(r"-\s*(\d+)", parse_str)
                                if end_day_match:
                                    end_day = end_day_match.group(1)
                                    deadline_iso = datetime.strptime(f"{month} {end_day} {season}", "%b %d %Y").replace(tzinfo=timezone.utc).isoformat()
                                else:
                                    # single day event
                                    deadline_iso = start_iso
                        except Exception as e:
                            logger.debug(f"Failed to parse MLH date '{date_str}': {e}")
                            
                    # Location
                    loc_tag = card.select_one(".event-location, [itemprop='address']")
                    location = loc_tag.text.strip() if loc_tag else "United States"
                    is_online = "online" in location.lower() or "virtual" in location.lower()
                    if is_online:
                        location = "Online"
                        
                    # Image
                    img_tag = card.select_one(".event-logo img, img[itemprop='image']")
                    image_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else None
                    if image_url and not image_url.startswith("http"):
                        image_url = f"https://mlh.io{image_url}"
                        
                    # MLH does not list prizes or descriptions directly on the cards,
                    # so we default them or add tags.
                    events.append({
                        "id": self.generate_hash(url_val),
                        "title": self.clean_string(title),
                        "url": url_val,
                        "platform": self.platform_name,
                        "hash": self.generate_hash(url_val),
                        "deadline": deadline_iso,
                        "registration_open_date": start_iso,
                        "image_url": image_url,
                        "prize_pool": "MLH Sponsor Prizes",
                        "location": location,
                        "is_online": is_online,
                        "country": "United States" if not is_online else None,
                        "theme": "Student Hackathon",
                        "organizer": "Major League Hacking",
                        "participants_count": None,
                        "difficulty": "Beginner friendly",
                        "description": f"Official student hackathon part of the MLH {season} season.",
                        "tags": ["mlh", "student", "hackathon"],
                        "team_required": False
                    })
                    
            except Exception as e:
                logger.error(f"Error scraping MLH season {season}: {e}")
                
        logger.info(f"Successfully collected {len(events)} hackathons from MLH.")
        return events
