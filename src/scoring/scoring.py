import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from loguru import logger
from pathlib import Path
import sys

# Add src to system path to import config
sys.path.append(str(Path(__file__).resolve().parents[2]))
import config

def parse_prize_amount(prize_str: Optional[str]) -> float:
    """
    Extracts a numeric value from a prize pool string.
    Example: "$50,000" -> 50000.0, "$10K" -> 10000.0, "100000 INR" -> 1200.0 (converted roughly), etc.
    """
    if not prize_str:
        return 0.0
    
    # Standardize string
    s = prize_str.upper().strip()
    if s in ["TBD", "TBA", "NOT SPECIFIED", "NO PRIZE", "FREE", "N/A"]:
        return 0.0

    # Extract all digits and decimal points, ignoring commas
    # Check for keywords like 'K', 'M' (e.g., $10K, $1M)
    multiplier = 1.0
    if 'K' in s:
        multiplier = 1000.0
    elif 'M' in s:
        multiplier = 1000000.0
        
    # Check for Indian Rupees (INR) and convert roughly to USD (1 USD = ~83 INR)
    inr_conversion = 1.0
    if 'INR' in s or '₹' in s:
        inr_conversion = 1.0 / 83.0

    # Extract first sequence of digits/decimals
    numbers = re.findall(r'\d+(?:\.\d+)?', s.replace(',', ''))
    if not numbers:
        return 0.0
        
    amount = float(numbers[0]) * multiplier * inr_conversion
    return amount

def calculate_prize_score(prize_str: Optional[str]) -> float:
    """Calculates the prize money score component (Max: 30 points)."""
    amount = parse_prize_amount(prize_str)
    
    # Scaling rules (out of 30)
    if amount >= 100000:
        return 30.0
    elif amount >= 50000:
        return 25.0
    elif amount >= 20000:
        return 20.0
    elif amount >= 10000:
        return 15.0
    elif amount >= 5000:
        return 10.0
    elif amount > 0:
        return 5.0
    else:
        return 0.0

def calculate_deadline_urgency_score(deadline_str: Optional[str]) -> float:
    """Calculates the deadline urgency component (Max: 20 points)."""
    if not deadline_str:
        return 10.0  # Default middle-ground score if no deadline
        
    try:
        deadline = datetime.fromisoformat(deadline_str)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        time_left = deadline - now
        hours_left = time_left.total_seconds() / 3600.0
        
        if hours_left <= 0:
            return 0.0  # Expired
        
        # Closer deadlines are more urgent, giving higher scores
        if hours_left <= 72:  # <= 3 days
            return 20.0
        elif hours_left <= 168:  # <= 7 days
            return 18.0
        elif hours_left <= 360:  # <= 15 days
            return 14.0
        elif hours_left <= 720:  # <= 30 days
            return 8.0
        else:
            return 4.0
    except Exception as e:
        logger.debug(f"Error parsing deadline in scoring: {e}")
        return 10.0

def calculate_online_score(is_online: bool) -> float:
    """Calculates online preference component (Max: 15 points)."""
    return 15.0 if is_online else 0.0

def calculate_participant_score(count: Optional[int]) -> float:
    """Calculates the participant count component (Max: 10 points) - lower count is preferred."""
    if count is None or count < 0:
        return 5.0  # Default middle ground
        
    if count < 100:
        return 10.0
    elif count < 500:
        return 7.0
    elif count < 1500:
        return 4.0
    else:
        return 1.0

def calculate_theme_relevance_score(title: str, tags: List[str], description: str) -> float:
    """Calculates the theme relevance component (Max: 15 points)."""
    title_lower = title.lower()
    desc_lower = (description or "").lower()
    tags_lower = [t.lower() for t in tags or []]
    
    max_score = 0.0
    
    # Scan all theme weights defined in config
    for theme, weight in config.THEME_WEIGHTS.items():
        # Check title
        if theme in title_lower:
            max_score = max(max_score, weight)
        # Check tags
        elif any(theme in tag for tag in tags_lower):
            max_score = max(max_score, weight)
        # Check description (half weight if ONLY in description, to prevent keyword stuffing)
        elif theme in desc_lower:
            max_score = max(max_score, weight * 0.7)
            
    return min(max_score, 15.0)

def calculate_popularity_score(platform: str, count: Optional[int]) -> float:
    """Calculates popularity component (Max: 10 points)."""
    # Base popularity by platform
    base_popularity = {
        "devpost": 8.0,
        "devfolio": 8.0,
        "mlh": 9.0,
        "google": 9.0,
        "microsoft": 9.0,
        "unstop": 7.0,
        "hack2skill": 6.0,
        "luma": 6.0,
        "ieee": 7.0
    }
    
    score = base_popularity.get(platform.lower(), 5.0)
    
    # Adjust slightly based on participant count if available
    if count is not None and count > 0:
        if count > 1500:
            score += 2.0
        elif count > 500:
            score += 1.0
        elif count < 100:
            score -= 1.0
            
    return max(0.0, min(score, 10.0))

def calculate_priority_score(h: Dict[str, Any]) -> float:
    """
    Calculates the aggregate priority score for a hackathon.
    Returns a score rounded to 1 decimal place.
    """
    # Calculate components
    prize = calculate_prize_score(h.get("prize_pool"))
    urgency = calculate_deadline_urgency_score(h.get("deadline"))
    online = calculate_online_score(h.get("is_online", False))
    participants = calculate_participant_score(h.get("participants_count"))
    
    # Extract tags (handles DB JSON text or parsed list)
    tags = h.get("tags", [])
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = [t.strip() for t in tags.split(",") if t.strip()]
            
    theme = calculate_theme_relevance_score(
        h.get("title", ""),
        tags,
        h.get("description", "")
    )
    popularity = calculate_popularity_score(h.get("platform", ""), h.get("participants_count"))
    
    # Apply weights (already calibrated out of component max values)
    total_score = prize + urgency + online + participants + theme + popularity
    
    # Safety clamp
    final_score = max(0.0, min(total_score, 100.0))
    return round(final_score, 1)
