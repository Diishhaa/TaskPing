# 🚀 Production-Ready Hackathon Tracker Daemon

An automated, serverless, and modular Hackathon Discovery and Notification system that polls multiple online platforms every 3 hours via **GitHub Actions**, scores hackathons according to custom priority criteria, sends real-time Telegram updates, dispatches daily summaries, and executes milestone deadline reminders.

---

## 📁 Repository Structure

```text
hackathon-tracker/
├── .github/
│   └── workflows/
│       └── tracker.yml         # GitHub Actions cron workflow
├── data/
│   ├── hackathons.db           # SQLite state-storage database (automatically created)
│   └── hackathons.csv          # Telemetry export file of all tracked events
├── logs/
│   └── tracker.log             # Rotating log file (local runs only)
├── src/
│   ├── collectors/
│   │   ├── base.py             # BaseCollector abstract interface & fetcher helper
│   │   ├── devpost.py          # Devpost API & HTML collector
│   │   ├── devfolio.py         # Devfolio API & HTML collector
│   │   ├── unstop.py           # Unstop Next.js prop JSON collector
│   │   ├── mlh.py              # MLH static season scheduler collector
│   │   ├── hack2skill.py       # Hack2Skill card scraper
│   │   ├── luma.py             # Lu.ma tech search scraper
│   │   ├── google.py           # Google Developer Events filter scraper
│   │   ├── microsoft.py        # Microsoft Developer Events scraper
│   │   └── ieee.py             # IEEE Student Competitions scraper
│   ├── database/
│   │   └── db.py               # SQLite connection, table schemas, and state managers
│   ├── scoring/
│   │   └── scoring.py          # Priority scoring engine (out of 100)
│   ├── telegram/
│   │   └── bot.py              # Asynchronous Telegram client & formatted templates
│   ├── utils/
│   │   ├── csv_exporter.py     # Writes SQLite database to data/hackathons.csv
│   │   └── stats.py            # Computes weekly statistics and discoveries
│   └── main.py                 # Core orchestrator and execution entrypoint
├── .env.example                # Example local environment settings
├── config.py                   # Central configuration & parameter weights
├── requirements.txt            # Python dependency definitions
└── README.md                   # Setup, setup instructions, and manual
```

---

## ⚡ Tech Stack

*   **Runtime:** Python 3.12
*   **Database:** SQLite (lightweight, filesystem-based serverless persistence)
*   **Libraries:**
    *   `requests` & `beautifulsoup4` & `lxml` for scrapers
    *   `pandas` for CSV generation and exports
    *   `python-telegram-bot` for async Telegram API interface
    *   `loguru` for enterprise rotating logging
    *   `python-dotenv` for config environment injection

---

## ⚙️ Setup and Installation

### 1. Prerequisites
Make sure you have **Python 3.12+** installed on your system.

### 2. Local Installation
Clone the repository, initialize a virtual environment, and install dependencies:

```bash
# Clone the repository
git clone <your-repo-url>
cd TaskPing

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory by copying the example:

```bash
cp .env.example .env
```

Open `.env` and fill in your Telegram credentials (see below for instructions on obtaining them):

```ini
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=-1001234567890
```

---

## 🤖 Telegram Bot Setup

To send notifications, you need a Telegram Bot and a Chat/Channel ID:

1.  **Create a Bot:**
    *   Open Telegram and search for [@BotFather](https://t.me/BotFather).
    *   Send `/newbot` and follow the instructions to name it.
    *   Copy the HTTP API **Token** and paste it as `TELEGRAM_BOT_TOKEN` in your `.env`.
2.  **Get Chat/Channel ID:**
    *   For a **Private Chat**: Send a message to your bot, then visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` in a browser. Find the `"chat": {"id": 123456789}` value.
    *   For a **Channel/Group**: Add the bot to your channel/group as an administrator. Send a message in the channel, then inspect `/getUpdates` to get the negative ID (e.g., `-1001234567890`). Paste this as `TELEGRAM_CHAT_ID` in `.env`.

---

## 🛠 Running Locally

The main orchestrator supports multiple command-line flags for dry-running, testing, or executing specific actions:

```bash
# Dry Run (Scrapes, filters, and scores events, but does NOT write to SQLite or send Telegram messages)
python src/main.py --dry-run

# Run full pipeline locally (will notify if credentials are set in .env)
python src/main.py

# Send the Daily Summary immediately
python src/main.py --summary-only

# Check and send upcoming reminders immediately
python src/main.py --reminders-only

# Send the Weekly Statistics report immediately
python src/main.py --stats-only
```

---

## 🥇 The Priority Scoring Engine

Hackathons are analyzed by `src/scoring/scoring.py` and awarded a score out of 100 based on the following weighted criteria:

1.  **Prize Money (30%)**: Scaled based on total prize pool (amounts >= $100k score 30/30, lower ranges score progressively less).
2.  **Deadline Urgency (20%)**: Higher urgency scores given as the deadline approaches (within 3 days scores 20/20, within 30 days scores 8/20).
3.  **Online Preferred (15%)**: Virtual/Online events receive a flat 15 points.
4.  **Lower Participant Count (10%)**: Promotes opportunities with higher odds of winning. Events with < 100 participants score 10/10; large events score less.
5.  **Theme Relevance (15%)**: Evaluated using matching keywords in title, tags, or description. Highly weighted themes: *AI, Generative AI, Machine Learning, Healthcare, FinTech, Cybersecurity, Blockchain, Climate Tech, Accessibility*.
6.  **Popularity (10%)**: Baseline score given by the host platform reputation and relative size.

All weights and theme keywords are fully customizable in `config.py`.

---

## 🔔 Notification Features

### 1. Instant Alerts
When a new hackathon is found (and its score is above the configured `MIN_SCORE_THRESHOLD`), an alert is sent:
*   🔥 **HIGH PRIORITY HACKATHON** (Score >= 70)
*   ⭐ **MEDIUM PRIORITY HACKATHON** (Score 40-69)
*   ⚪ **LOW PRIORITY HACKATHON** (Score < 40, muted by default unless threshold is lowered)

Alerts contain inline buttons:
*   `Register`: Direct link to the event.
*   `Platform`: Direct link to the aggregator platform.
*   `Share`: Quick link to share the event with colleagues on Telegram.

### 2. Keyword Alerts
If any specialized keyword (e.g. *Gemini, LLM, OpenCV, Web3, Android*) is found inside the title or description, an additional **🔍 KEYWORD MATCH** alert is sent immediately, ignoring the threshold requirements.

### 3. Milestone Reminders
For registered hackathons, the scheduler tracks deadlines and automatically dispatches reminders:
*   ⏰ **7 Days** before deadline
*   ⏰ **3 Days** before deadline
*   🚨 **24 Hours** before deadline
*   🛑 **Final 3 Hours** before deadline

### 4. Daily Summary
Dispatched automatically once per day (after 9:00 AM local time). It reports the counts of active hackathons (High/Medium/Low priority), list of Top 5 Recommendations, and upcoming deadlines in the next 7 days.

---

## 🚀 GitHub Actions Setup (Serverless Cron Daemon)

To run the tracker automatically in GitHub Actions without keeping a local computer turned on:

1.  Push the repository to GitHub.
2.  Go to your repository on GitHub: **Settings > Secrets and variables > Actions**.
3.  Click **New repository secret** and add:
    *   `TELEGRAM_BOT_TOKEN`: Your bot token
    *   `TELEGRAM_CHAT_ID`: Your chat or channel ID
4.  Go to **Settings > Actions > General > Workflow permissions** and select **Read and write permissions**. Click **Save** (this allows the bot to commit database and CSV updates back to the repo).

The workflow (`.github/workflows/tracker.yml`) is scheduled to run every 3 hours. On each run, it queries all platforms, updates the SQLite database file (`data/hackathons.db`), updates the CSV (`data/hackathons.csv`), and pushes changes back to the repository.

---

## 🧩 Adding a New Collector

To add a new platform collector:

1.  Create a new file in `src/collectors/` named after the platform (e.g., `myplatform.py`).
2.  Inherit from `BaseCollector` and implement the `collect(self) -> List[Dict[str, Any]]` method. Use the unified schema.
3.  Example template:

```python
from src.collectors.base import BaseCollector
from typing import List, Dict, Any

class MyPlatformCollector(BaseCollector):
    def __init__(self):
        super().__init__("MyPlatform")
        self.url = "https://myplatform.com/hackathons"

    def collect(self) -> List[Dict[str, Any]]:
        response = self.fetch_url(self.url)
        if not response:
            return []
        
        events = []
        # Parse logic here...
        # events.append({ "id": ..., "title": ..., "url": ... })
        return events
```

4.  Import and instantiate the collector in `src/main.py`.
5.  Enable/disable the platform in `config.py` by adding it to the `ENABLED_PLATFORMS` dictionary.

---

## 🔧 Troubleshooting

### Local Run Errors
*   **ModuleNotFoundError**: Ensure your virtual environment is active and that you installed all packages listed in `requirements.txt` via `pip install -r requirements.txt`.
*   **Bot token not found**: Verify that the `.env` file exists in the root directory and holds correct values.

### GitHub Actions Errors
*   **Permission Error on Git Push**: Ensure that the "Workflow permissions" in the repo settings are set to **Read and Write**. Without this, the cron job will fail to commit state changes.
*   **Duplicate Notifications**: If Git push fails, the SQLite database state is not saved. Subsequent runs will treat already-alerted events as "new" and send duplicates. Ensure the push step completes successfully.