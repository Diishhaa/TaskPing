import asyncio
import json
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from loguru import logger
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
import config

class TelegramNotifier:
    """
    Manages Telegram bot notifications including instant alerts, 
    reminders, daily summaries, and weekly statistics.
    Runs asynchronously and supports a Dry-Run/Mock mode.
    """
    
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.is_mock = not (self.bot_token and self.chat_id)
        
        if self.is_mock:
            logger.warning("Telegram Bot Token or Chat ID not found in environment. Running in Dry Run / Mock Mode.")
            self.bot = None
        else:
            # Initialize python-telegram-bot
            self.bot = Bot(token=self.bot_token)
            logger.info("Telegram Bot client initialized successfully.")

    def _get_platform_url(self, platform: str) -> str:
        """Helper to get platform landing page URLs."""
        urls = {
            "devpost": "https://devpost.com",
            "devfolio": "https://devfolio.co",
            "unstop": "https://unstop.com",
            "mlh": "https://mlh.io",
            "hack2skill": "https://hack2skill.com",
            "luma": "https://lu.ma",
            "google": "https://developers.google.com/events",
            "microsoft": "https://developer.microsoft.com/en-us/events",
            "ieee": "https://www.ieee.org"
        }
        return urls.get(platform.lower(), "https://google.com")

    def _escape_markdown(self, text: str) -> str:
        """Escapes special characters for Telegram's Markdown (legacy V1)."""
        if not text:
            return ""
        # Legacy markdown V1 requires less escaping than V2:
        # Just escape '_', '*', '`', '['.
        escape_chars = r'_*`['
        return re.sub(r'([' + re.escape(escape_chars) + r'])', r'\\\1', str(text))

    def _build_hackathon_message(self, h: Dict[str, Any], header: str) -> str:
        """Formats a hackathon alert into a beautiful Markdown message."""
        title = h.get("title", "Unnamed Hackathon")
        platform = h.get("platform", "Unknown")
        prize = h.get("prize_pool") or "TBD"
        
        # Format deadline
        deadline_str = "TBD"
        if h.get("deadline"):
            try:
                dt = datetime.fromisoformat(h["deadline"])
                deadline_str = dt.strftime("%Y-%m-%d %H:%M UTC")
            except:
                deadline_str = h["deadline"]
                
        location = h.get("location") or "Unknown"
        mode = "💻 Online" if h.get("is_online") else "🏢 In-Person"
        score = h.get("priority_score", 0.0)
        
        # Tags/Themes
        tags = h.get("tags") or []
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except:
                tags = [t.strip() for t in tags.split(",") if t.strip()]
        themes = ", ".join(tags[:4]) if tags else h.get("theme") or "General"
        
        msg = (
            f"{header}\n\n"
            f"🏆 *Name:* {title}\n"
            f"🌍 *Platform:* {platform}\n"
            f"💰 *Prize:* {prize}\n"
            f"📅 *Deadline:* {deadline_str}\n"
            f"📍 *Location:* {location}\n"
            f"💻 *Mode:* {mode}\n"
            f"⭐ *Priority Score:* {score}/100\n"
            f"🏷 *Themes:* {themes}\n"
        )
        return msg

    def _build_inline_keyboard(self, url: str, platform_url: str, title: str) -> InlineKeyboardMarkup:
        """Creates the Register, Platform, and Share inline buttons."""
        share_text = f"Check out this hackathon: {title} on {url}!"
        share_url = f"https://t.me/share/url?url={urllib.parse.quote(url)}&text={urllib.parse.quote(share_text)}"
        
        keyboard = [
            [
                InlineKeyboardButton("🔗 Register", url=url),
                InlineKeyboardButton("🌍 Platform", url=platform_url)
            ],
            [
                InlineKeyboardButton("📢 Share", url=share_url)
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def send_message(self, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
        """Sends a generic markdown message to the Telegram channel."""
        if self.is_mock:
            logger.info(f"[MOCK TELEGRAM MESSAGE]\n{text}")
            if reply_markup:
                # Log button details
                buttons = []
                for row in reply_markup.inline_keyboard:
                    buttons.append(", ".join(f"[{b.text} -> {b.url}]" for b in row))
                logger.info(f"[MOCK BUTTONS] { ' | '.join(buttons) }")
            return True
            
        try:
            # We run the Bot API call inside run_in_executor to avoid blocking the loop
            # python-telegram-bot's Bot is async in 20.x, so we can await it directly.
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
                disable_web_page_preview=False
            )
            logger.info("Message sent successfully to Telegram.")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_hackathon_alert(self, h: Dict[str, Any], is_keyword_match: bool = False) -> bool:
        """Sends an instant alert for a newly discovered hackathon."""
        score = h.get("priority_score", 0.0)
        
        # Select appropriate header
        if is_keyword_match:
            header = "🔍 *KEYWORD MATCH HACKATHON*"
        elif score >= 70:
            header = "🔥 *HIGH PRIORITY HACKATHON*"
        elif score >= 40:
            header = "⭐ *MEDIUM PRIORITY HACKATHON*"
        else:
            header = "⚪ *LOW PRIORITY HACKATHON*"
            
        msg = self._build_hackathon_message(h, header)
        platform_url = self._get_platform_url(h.get("platform", ""))
        keyboard = self._build_inline_keyboard(h["url"], platform_url, h.get("title", ""))
        
        return await self.send_message(msg, reply_markup=keyboard)

    async def send_reminder_alert(self, h: Dict[str, Any], reminder_level: str) -> bool:
        """Sends a milestone reminder alert (7d, 3d, 24h, 3h)."""
        time_headers = {
            "7d": "⏰ *DEADLINE REMINDER: 7 DAYS LEFT*",
            "3d": "⏰ *DEADLINE REMINDER: 3 DAYS LEFT*",
            "24h": "🚨 *URGENT REMINDER: 24 HOURS LEFT*",
            "3h": "🛑 *FINAL WARNING: 3 HOURS REMAINING*"
        }
        header = time_headers.get(reminder_level, "⏰ *DEADLINE REMINDER*")
        msg = self._build_hackathon_message(h, header)
        platform_url = self._get_platform_url(h.get("platform", ""))
        keyboard = self._build_inline_keyboard(h["url"], platform_url, h.get("title", ""))
        
        return await self.send_message(msg, reply_markup=keyboard)

    async def send_daily_summary(self, stats: Dict[str, Any], 
                                 recommendations: List[Dict[str, Any]], 
                                 deadlines: List[Dict[str, Any]]) -> bool:
        """Sends a morning daily summary of active hackathons and deadlines."""
        now_str = datetime.now().strftime("%A, %B %d, %Y")
        
        # Calculate priorities counts
        high = stats.get("high_priority_count", 0)
        medium = stats.get("medium_priority_count", 0)
        low = stats.get("low_priority_count", 0)
        total = stats.get("total_count", 0)
        
        msg = (
            f"📅 *Today's Hackathons Summary*\n"
            f"_{now_str}_\n\n"
            f"📊 *Opportunity Breakdown:*\n"
            f"🔥 {high} High Priority\n"
            f"⭐ {medium} Medium Priority\n"
            f"⚪ {low} Low Priority\n"
            f"📁 Total Tracked: {total}\n\n"
            f"🌟 *Top 5 Recommendations:*\n"
        )
        
        for i, rec in enumerate(recommendations, 1):
            title = rec.get("title", "")
            score = rec.get("priority_score", 0.0)
            platform = rec.get("platform", "")
            url = rec.get("url", "")
            msg += f"{i}\\. [{title}]({url}) \\- *{score}* ({platform})\n"
            
        msg += "\n⏳ *Upcoming Deadlines:*\n"
        if not deadlines:
            msg += "No deadlines in the next 7 days\\.\n"
        else:
            for deadline in deadlines:
                title = deadline.get("title", "")
                url = deadline.get("url", "")
                dl_val = deadline.get("deadline")
                try:
                    dt = datetime.fromisoformat(dl_val)
                    dl_str = dt.strftime("%b %d")
                except:
                    dl_str = str(dl_val)
                msg += f"• [{title}]({url}) \\- *{dl_str}*\n"
                
        # Send summary
        return await self.send_message(msg)

    async def send_weekly_stats(self, stats: Dict[str, Any], new_count: int) -> bool:
        """Sends weekly telemetry statistics."""
        msg = (
            f"📈 *Weekly Telemetry Statistics*\n\n"
            f"✨ Discovered {new_count} new hackathons this week\\!\n"
            f"🗂 Total Tracked: {stats.get('total_count', 0)}\n\n"
            f"🔌 *Distribution by Platform:*\n"
        )
        
        for plat, count in stats.get("by_platform", {}).items():
            msg += f"• {plat}: {count}\n"
            
        return await self.send_message(msg)
