import time
import hashlib
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from loguru import logger
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
import config

class BaseCollector(ABC):
    """
    Abstract Base Class for all hackathon scrapers/collectors.
    Provides common networking utility methods with retry and backoff logic.
    """
    
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive"
        }
        self.session.headers.update(self.headers)

    @abstractmethod
    def collect(self) -> List[Dict[str, Any]]:
        """
        Fetches events from the platform, parses them into a common dictionary schema,
        and returns them. Should not raise errors; catch and log them instead.
        """
        pass

    def fetch_url(self, url: str, method: str = "GET", 
                  params: Optional[Dict[str, Any]] = None, 
                  json_data: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None) -> Optional[requests.Response]:
        """
        Fetches a URL with retries, timeout, and exponential backoff.
        """
        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)
            
        retries = config.MAX_RETRIES
        backoff = config.BACKOFF_FACTOR
        
        for attempt in range(1, retries + 1):
            try:
                if method.upper() == "POST":
                    response = self.session.post(
                        url, params=params, json=json_data, 
                        headers=req_headers, timeout=config.REQUEST_TIMEOUT
                    )
                else:
                    response = self.session.get(
                        url, params=params, 
                        headers=req_headers, timeout=config.REQUEST_TIMEOUT
                    )
                
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(
                    f"[{self.platform_name}] HTTP {method} failed on {url} (Attempt {attempt}/{retries}): {e}"
                )
                if attempt == retries:
                    logger.error(f"[{self.platform_name}] Max retries reached for {url}.")
                    return None
                time.sleep(backoff ** attempt)
        return None

    def generate_hash(self, text: str) -> str:
        """Generates a SHA-256 hash of a string, useful for deduplication IDs."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def clean_string(self, text: Optional[str]) -> str:
        """Helper to trim and sanitize text."""
        if not text:
            return ""
        return " ".join(text.split())
