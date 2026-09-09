from integrations.base_agent import BaseAgent
from schemas.episodic_memory import (
    ChatHistoryMessage,
    EpisodicCreatorResult,
    EpisodicMemoryCreatorState,
)

from configs.settings import EPISODIC_MEMORY_PROMPT_PATH


class EpisodicMemoryCreator:
    """Decides whether a session is worth remembering and extracts episodes."""

    def __init__(self, agent: BaseAgent | None = None) -> None:
        self.agent = agent or BaseAgent(
            system_prompt=EPISODIC_MEMORY_PROMPT_PATH.read_text(
                encoding="utf-8"
            ),
            response_model=EpisodicCreatorResult,
        )

    def create(
        self,
        chat_history: list[ChatHistoryMessage],
    ) -> EpisodicCreatorResult:
        state: EpisodicMemoryCreatorState = {
            "chat_history": chat_history,
            "relevant_context": {
                "episodic_memory": [],
                "semantic_memory": [],
                "procedural_memory": [],
            },
        }
        response = self.agent.invoke(state)
        if response.error:
            return response
        return response