from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.database import db

def get_weekly_stats() -> Dict[str, Any]:
    """
    Calculates statistics for hackathons added in the last 7 days.
    """
    logger.info("Generating weekly statistics...")
    stats = {
        "new_count": 0,
        "by_platform": {},
        "avg_score": 0.0,
        "high_priority_count": 0
    }
    
    try:
        all_events = db.export_all_hackathons()
        now = datetime.now(timezone.utc)
        one_week_ago = now - timedelta(days=7)
        
        new_events = []
        for e in all_events:
            try:
                first_seen = datetime.fromisoformat(e["first_seen"])
                if first_seen.tzinfo is None:
                    first_seen = first_seen.replace(tzinfo=timezone.utc)
                    
                if first_seen >= one_week_ago:
                    new_events.append(e)
            except Exception as ex:
                logger.debug(f"Failed parsing first_seen for stats: {ex}")
                continue
                
        stats["new_count"] = len(new_events)
        if not new_events:
            return stats
            
        # Group by platform
        platforms = {}
        total_score = 0.0
        high_priority = 0
        
        for e in new_events:
            p = e["platform"]
            platforms[p] = platforms.get(p, 0) + 1
            
            score = e.get("priority_score", 0.0)
            total_score += score
            if score >= 70:
                high_priority += 1
                
        stats["by_platform"] = platforms
        stats["avg_score"] = round(total_score / len(new_events), 1)
        stats["high_priority_count"] = high_priority
        
        logger.info(f"Weekly stats generated: {stats['new_count']} new opportunities found.")
    except Exception as e:
        logger.error(f"Failed to generate weekly stats: {e}")
        
    return stats
