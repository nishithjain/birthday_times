# backend/config.py
"""Configuration management for Birthday Chronicles."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration."""
    
    # Database
    database_path: Path = field(default_factory=lambda: Path("backend/database/birthday_chronicles.db"))
    schema_path: Path = field(default_factory=lambda: Path("backend/database/schema.sql"))
    
    # Wikidata
    wikidata_endpoint: str = "https://query.wikidata.org/sparql"
    wikidata_user_agent: str = "BirthdayChronicles/0.3 (Historical birthday information application)"
    wikidata_timeout: int = 60
    wikidata_retries: int = 3
    wikidata_rate_limit: float = 1.0  # seconds between requests
    
    # Default user preferences
    default_country: str = "India"
    default_language: str = "en"
    
    # Import settings
    import_batch_size: int = 100
    minimum_importance_score: int = 3
    
    # API Keys
    tmdb_api_key: Optional[str] = None
    musicbrainz_user_agent: str = "BirthdayChronicles/0.3"
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None
    
    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "Config":
        """Load configuration from environment variables."""
        if env_file and env_file.exists():
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        config = cls()
        
        # Override with environment variables
        if os.getenv("DATABASE_PATH"):
            config.database_path = Path(os.getenv("DATABASE_PATH"))
        
        if os.getenv("WIKIDATA_ENDPOINT"):
            config.wikidata_endpoint = os.getenv("WIKIDATA_ENDPOINT")
        
        if os.getenv("WIKIDATA_USER_AGENT"):
            config.wikidata_user_agent = os.getenv("WIKIDATA_USER_AGENT")
        
        if os.getenv("DEFAULT_COUNTRY"):
            config.default_country = os.getenv("DEFAULT_COUNTRY")
        
        config.tmdb_api_key = os.getenv("TMDB_API_KEY")
        
        if os.getenv("LOG_LEVEL"):
            config.log_level = os.getenv("LOG_LEVEL")
        
        if os.getenv("LOG_FILE"):
            config.log_file = Path(os.getenv("LOG_FILE"))
        
        return config
    
    def ensure_database_dir(self) -> None:
        """Ensure the database directory exists."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


# Global configuration instance
config = Config.from_env()