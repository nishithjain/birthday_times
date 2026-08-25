# backend/importers/base.py
"""Base importer class for Birthday Chronicles."""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import date

logger = logging.getLogger(__name__)


class BaseImporter(ABC):
    """Base class for all importers."""
    
    def __init__(self, source: str = "unknown"):
        self.source = source
        self.stats = {
            "total": 0,
            "accepted": 0,
            "rejected": 0,
            "errors": 0,
        }
    
    @abstractmethod
    def fetch(self, target_date: date, **kwargs) -> List[Any]:
        """Fetch data from source."""
        pass
    
    @abstractmethod
    def save(self, data: List[Any]) -> int:
        """Save data to database."""
        pass
    
    def import_date(self, target_date: date, dry_run: bool = False, **kwargs) -> Dict[str, int]:
        """Import data for a specific date."""
        self.stats = {"total": 0, "accepted": 0, "rejected": 0, "errors": 0}
        
        try:
            logger.info(f"Fetching data for {target_date} from {self.source}...")
            data = self.fetch(target_date, **kwargs)
            self.stats["total"] = len(data)
            
            if not data:
                logger.info("No data found.")
                return self.stats
            
            if dry_run:
                logger.info(f"Dry run: {len(data)} items would be saved.")
                self.stats["accepted"] = len(data)
                return self.stats
            
            count = self.save(data)
            self.stats["accepted"] = count
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            self.stats["errors"] = 1
        
        return self.stats