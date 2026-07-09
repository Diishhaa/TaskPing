import time
import schedule
import subprocess
import sys
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent))

import config

def run_tracker():
    logger.info("Scheduler: Triggering tracker execution...")
    try:
        # Run main.py using the current python interpreter
        result = subprocess.run([sys.executable, "src/main.py"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Scheduler: Tracker completed successfully.")
        else:
            logger.error(f"Scheduler: Tracker failed with exit code {result.returncode}.\nStderr: {result.stderr}")
    except Exception as e:
        logger.error(f"Scheduler: Failed to spawn tracker process: {e}")

def main():
    logger.info(f"Scheduler: Starting local daemon. Interval: {config.POLLING_INTERVAL_HOURS} hours.")
    # Run once immediately on start
    run_tracker()
    
    # Schedule subsequent runs
    schedule.every(config.POLLING_INTERVAL_HOURS).hours.do(run_tracker)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Scheduler: Stopped by user.")
            break
        except Exception as e:
            logger.error(f"Scheduler: Error in main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
