"""Native JARVIS integration of the Research Subsystem."""

from .research_workflow import invoke_research_subsystem
from .types import ResearchResult

__all__ = ["ResearchResult", "invoke_research_subsystem"]