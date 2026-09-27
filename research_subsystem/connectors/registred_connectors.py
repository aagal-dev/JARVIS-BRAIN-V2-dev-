# Connector runtime imports 
from .connector_registry import ConnectorRegistry

# Connectors imports
from .github import GitHubConnector
from .news import NewsConnector
from .web_scraper_v3_tavily import WebScraperConnector
from .research_papers import ResearchPapersConnector
from .youtube_connector_v1 import YouTubeConnector

connector_registry = ConnectorRegistry()
    
# Registering connectors
connector_registry.register(GitHubConnector())
connector_registry.register(NewsConnector())
connector_registry.register(WebScraperConnector())
connector_registry.register(ResearchPapersConnector())
connector_registry.register(YouTubeConnector())
