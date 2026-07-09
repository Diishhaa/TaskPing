import json
import pandas as pd
from pathlib import Path
from loguru import logger
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
import config
from src.database import db

def export_db_to_csv():
    """Fetches all hackathons from SQLite and writes them to a clean CSV file."""
    logger.info("Exporting database records to CSV...")
    try:
        hackathons = db.export_all_hackathons()
        if not hackathons:
            logger.info("No hackathons found in database to export.")
            # Create an empty CSV with headers
            cols = [
                "id", "title", "url", "platform", "priority_score", "deadline", 
                "registration_open_date", "prize_pool", "location", "is_online", 
                "country", "theme", "organizer", "participants_count", "difficulty", 
                "description", "tags", "team_required", "first_seen", "last_seen"
            ]
            df = pd.DataFrame(columns=cols)
            config.CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(config.CSV_PATH, index=False)
            return

        # Load into DataFrame
        df = pd.DataFrame(hackathons)
        
        # Clean and format columns
        # Convert tags from JSON string to comma-separated string
        def format_tags(tags_val):
            if not tags_val:
                return ""
            try:
                parsed = json.loads(tags_val)
                if isinstance(parsed, list):
                    return ", ".join(parsed)
            except Exception:
                pass
            return str(tags_val)
            
        if "tags" in df.columns:
            df["tags"] = df["tags"].apply(format_tags)
            
        # Reorder/select columns to present to users nicely
        columns_to_keep = [
            "title", "platform", "priority_score", "deadline", "prize_pool", 
            "location", "is_online", "theme", "organizer", "participants_count", 
            "difficulty", "team_required", "url", "tags", "description", "first_seen"
        ]
        
        # Keep only existing columns
        columns_to_keep = [col for col in columns_to_keep if col in df.columns]
        df_export = df[columns_to_keep]
        
        # Ensure directory exists
        config.CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_export.to_csv(config.CSV_PATH, index=False)
        logger.info(f"Successfully exported {len(df_export)} hackathons to {config.CSV_PATH}")
    except Exception as e:
        logger.error(f"Failed to export database to CSV: {e}")
