import argparse
import asyncio
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from loguru import logger
import sys

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import config
from src.database import db
from src.scoring import scoring
from src.telegram.bot import TelegramNotifier
from src.utils import csv_exporter, stats

# Import collectors
from src.collectors.devpost import DevpostCollector
from src.collectors.devfolio import DevfolioCollector
from src.collectors.unstop import UnstopCollector
from src.collectors.mlh import MlhCollector
from src.collectors.hack2skill import Hack2SkillCollector
from src.collectors.luma import LumaCollector
from src.collectors.google import GoogleCollector
from src.collectors.microsoft import MicrosoftCollector
from src.collectors.ieee import IeeeCollector

def setup_logging():
    """Configures the Loguru logger."""
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = config.LOGS_DIR / "tracker.log"
    
    # Remove default handler and add custom layout
    logger.remove()
    logger.add(
        sys.stdout, 
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        str(log_file),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:7} | {name}:{function} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8"
    )
    logger.info("Logging configured successfully.")

def is_expired(deadline_str: str) -> bool:
    """Checks if a deadline is in the past."""
    if not deadline_str:
        return False
    try:
        deadline = datetime.fromisoformat(deadline_str)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return deadline < datetime.now(timezone.utc)
    except:
        return False

def contains_keyword(text: str) -> bool:
    """Checks if text contains any of the configured alert keywords."""
    if not text:
        return False
    text_lower = text.lower()
    for kw in config.ALERT_KEYWORDS:
        # Use word boundaries or simple substring search
        if kw.lower() in text_lower:
            return True
    return False

async def run_pipeline(dry_run: bool = False):
    """Executes the core hackathon discovery and notification pipeline."""
    logger.info("Starting Hackathon Tracker Pipeline...")
    
    # 1. Initialize SQLite Database
    db.init_db()
    
    # 2. Instantiate active collectors
    collectors = []
    if config.ENABLED_PLATFORMS.get("devpost"):
        collectors.append(DevpostCollector())
    if config.ENABLED_PLATFORMS.get("devfolio"):
        collectors.append(DevfolioCollector())
    if config.ENABLED_PLATFORMS.get("unstop"):
        collectors.append(UnstopCollector())
    if config.ENABLED_PLATFORMS.get("mlh"):
        collectors.append(MlhCollector())
    if config.ENABLED_PLATFORMS.get("hack2skill"):
        collectors.append(Hack2SkillCollector())
    if config.ENABLED_PLATFORMS.get("luma"):
        collectors.append(LumaCollector())
    if config.ENABLED_PLATFORMS.get("google"):
        collectors.append(GoogleCollector())
    if config.ENABLED_PLATFORMS.get("microsoft"):
        collectors.append(MicrosoftCollector())
    if config.ENABLED_PLATFORMS.get("ieee"):
        collectors.append(IeeeCollector())
        
    logger.info(f"Loaded {len(collectors)} active collectors.")
    
    # 3. Collect raw events from all platforms
    raw_events = []
    for c in collectors:
        try:
            logger.info(f"Running collector: {c.platform_name}")
            col_events = c.collect()
            raw_events.extend(col_events)
            logger.info(f"[{c.platform_name}] Found {len(col_events)} events.")
        except Exception as e:
            logger.error(f"[{c.platform_name}] Collector failed: {e}")
            continue
            
    logger.info(f"Total raw events collected: {len(raw_events)}")
    
    # 4. Filter and score events
    valid_events = []
    for event in raw_events:
        # Filter 1: Missing registration URL
        if not event.get("url"):
            logger.debug(f"Filtered out (missing registration link): {event.get('title')}")
            continue
            
        # Filter 2: Expired events
        if event.get("deadline") and is_expired(event["deadline"]):
            logger.debug(f"Filtered out (expired): {event.get('title')} - Deadline: {event['deadline']}")
            continue
            
        # Filter 3: Cancelled events
        if "cancel" in event.get("title", "").lower() or "cancel" in event.get("description", "").lower():
            logger.debug(f"Filtered out (cancelled): {event.get('title')}")
            continue
            
        # Score the event
        score = scoring.calculate_priority_score(event)
        event["priority_score"] = score
        
        valid_events.append(event)
        
    logger.info(f"Total valid events after filtering: {len(valid_events)}")
    
    # If dry run, print results and exit
    if dry_run:
        logger.info("[DRY RUN] Scored events preview:")
        for idx, event in enumerate(sorted(valid_events, key=lambda x: x["priority_score"], reverse=True)[:15], 1):
            logger.info(f"{idx}. [{event['platform']}] {event['title']} - Score: {event['priority_score']} - Prize: {event['prize_pool']} - Online: {event['is_online']}")
        csv_exporter.export_db_to_csv()
        logger.info("[DRY RUN] Complete. No database modifications or Telegram notifications dispatched.")
        return
        
    # 5. Sync with Database
    new_count = db.save_hackathons(valid_events)
    
    # 6. Initialize Telegram Notifier
    notifier = TelegramNotifier()
    
    # 7. Process Initial Notifications
    unnotified = db.get_unnotified_hackathons()
    logger.info(f"Processing notifications for {len(unnotified)} unnotified events...")
    
    for h in unnotified:
        # Verify score passes minimum config threshold before sending main alert
        score = h.get("priority_score", 0.0)
        
        if score >= config.MIN_SCORE_THRESHOLD:
            # Send high/medium/low priority notification
            success = await notifier.send_hackathon_alert(h)
            if success:
                db.mark_as_notified(h["url"])
        else:
            # If below threshold, mark notified in DB to ignore, keeping logs silent
            logger.debug(f"Skipping main notification for '{h['title']}' (Score {score} < {config.MIN_SCORE_THRESHOLD})")
            db.mark_as_notified(h["url"])
            
        # 8. Check for Keyword Alerts (triggers independent of score threshold)
        title = h.get("title", "")
        desc = h.get("description", "")
        tags = h.get("tags", "")
        
        full_text = f"{title} {desc} {tags}"
        if contains_keyword(full_text) and not h.get("keyword_match_sent"):
            logger.info(f"Keyword match triggered for '{title}'!")
            success = await notifier.send_hackathon_alert(h, is_keyword_match=True)
            if success:
                db.mark_keyword_match_as_notified(h["url"])
                
    # 9. Process Milestone Reminders
    reminders = db.get_upcoming_reminders()
    logger.info(f"Processing {len(reminders)} due milestone reminders...")
    for h, level in reminders:
        logger.info(f"Sending {level} reminder for '{h['title']}'...")
        success = await notifier.send_reminder_alert(h, level)
        if success:
            db.mark_reminder_as_sent(h["url"], level)
            
    # 10. Check Daily Summary Window
    # If current local time is past 9:00 AM (local time) and summary wasn't sent today
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    last_summary_date = db.get_setting("last_daily_summary_date")
    
    if now.hour >= 9 and last_summary_date != today_str:
        logger.info("Triggering Daily Summary dispatch...")
        system_stats = db.get_stats()
        recommendations = db.get_recommendations(limit=5)
        deadlines = db.get_upcoming_deadlines(limit=5)
        
        success = await notifier.send_daily_summary(system_stats, recommendations, deadlines)
        if success:
            db.set_setting("last_daily_summary_date", today_str)
            logger.info("Daily Summary marked as sent for today.")
            
    # 11. Check Weekly Stats Window (triggered every Sunday or if 7 days elapsed)
    last_weekly_date_str = db.get_setting("last_weekly_stats_date")
    should_send_weekly = False
    
    if not last_weekly_date_str:
        # Send on first run if Sunday
        should_send_weekly = (now.weekday() == 6)  # Sunday
    else:
        try:
            last_weekly = datetime.fromisoformat(last_weekly_date_str)
            # Send if Sunday and at least 6 days elapsed since last weekly stats
            should_send_weekly = (now.weekday() == 6) and (now - last_weekly >= timedelta(days=6))
        except:
            should_send_weekly = (now.weekday() == 6)
            
    if should_send_weekly:
        logger.info("Triggering Weekly Telemetry Stats dispatch...")
        weekly_stats = stats.get_weekly_stats()
        system_stats = db.get_stats()
        success = await notifier.send_weekly_stats(system_stats, weekly_stats.get("new_count", 0))
        if success:
            db.set_setting("last_weekly_stats_date", now.isoformat())
            logger.info("Weekly telemetry stats marked as sent.")
            
    # 12. Export Database to CSV
    csv_exporter.export_db_to_csv()
    logger.info("Hackathon Tracker Pipeline execution finished.")

def main():
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Hackathon Tracker & Telegram Notifier Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Queries and scores events without saving to DB or notifying.")
    parser.add_argument("--summary-only", action="store_true", help="Dispatches the daily summary alert immediately.")
    parser.add_argument("--reminders-only", action="store_true", help="Runs the deadline reminder check only.")
    parser.add_argument("--stats-only", action="store_true", help="Runs the weekly stats check only.")
    
    args = parser.parse_args()
    
    # Helper to run async tasks from sync context
    loop = asyncio.get_event_loop()
    
    if args.summary_only:
        db.init_db()
        notifier = TelegramNotifier()
        system_stats = db.get_stats()
        recommendations = db.get_recommendations(limit=5)
        deadlines = db.get_upcoming_deadlines(limit=5)
        loop.run_until_complete(notifier.send_daily_summary(system_stats, recommendations, deadlines))
    elif args.reminders_only:
        db.init_db()
        notifier = TelegramNotifier()
        reminders = db.get_upcoming_reminders()
        for h, level in reminders:
            loop.run_until_complete(notifier.send_reminder_alert(h, level))
            db.mark_reminder_as_sent(h["url"], level)
    elif args.stats_only:
        db.init_db()
        notifier = TelegramNotifier()
        weekly_stats = stats.get_weekly_stats()
        system_stats = db.get_stats()
        loop.run_until_complete(notifier.send_weekly_stats(system_stats, weekly_stats.get("new_count", 0)))
    else:
        loop.run_until_complete(run_pipeline(dry_run=args.dry_run))

if __name__ == "__main__":
    main()
