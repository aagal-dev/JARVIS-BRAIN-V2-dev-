from datetime import datetime, timezone
from core.agentic_loop import JarvisBrain
from schemas.orchestrator.orchestrator_v2 import OrchestratorResult, ConversationAgentHandoff
from schemas.agents.conversation_agent import ConversationAgentOutput
from schemas.episodic_memory import EpisodicEpisode
from integrations.qdrant_client import QdrantClient
from schemas.agents.planner_v2 import PlannerResult, PlannerState
from memory.retrieval import MemoryRetrieval, MemoryRetrievalResult

# Dummy planner that returns a direct mode response
def dummy_planner(state: PlannerState) -> PlannerResult:
    return PlannerResult(mode="direct", objective=None, steps=[], error=None)

# Dummy orchestrator that always asks the conversation agent to respond
def dummy_orchestrator(runtime_state, available_components):
    # runtime_state is a dict representation
    user_req = runtime_state.get("user_request", "")
    handoff = ConversationAgentHandoff(user_request=user_req, objective="")
    return OrchestratorResult(next_step="respond", conversation_agent_handoff=handoff)

# Dummy conversation agent that returns a fixed response
def dummy_conversation_agent(state) -> ConversationAgentOutput:
    return ConversationAgentOutput(response="This is a test response.", response_type="answer")

import tempfile
from memory.episodic.storage import EpisodicMemoryStore
from memory.episodic.service import EpisodicMemoryService

temp_dir = tempfile.TemporaryDirectory()
clean_store = EpisodicMemoryStore(temp_dir.name)

episode1 = EpisodicEpisode(
    type="project",
    summary="The architecture decision is to use a microservice design.",
    state="active",
    change="",
    outcome="",
    importance=0.9,
    confidence=0.95,
    tags=["architecture"],
)
clean_store.create(episode1, timestamp=datetime.now(timezone.utc))

class EmptyRetrieval:
    def retrieve(self, query):
        return MemoryRetrievalResult(query=query, results=[])
    def index_record(self, record):
        return None
    def rebuild_index(self):
        return []

episode2 = EpisodicEpisode(
    type="project",
    summary="User interface will use dark mode.",
    state="active",
    change="",
    outcome="",
    importance=0.5,
    confidence=0.8,
    tags=["ui"],
)
clean_store.create(episode2, timestamp=datetime.now(timezone.utc))

brain = JarvisBrain(
    planner=dummy_planner,
    orchestrator=dummy_orchestrator,
    conversation_agent=dummy_conversation_agent,
    episodic_memory=EpisodicMemoryService(
        creator=None,  # not used in this test
        store=clean_store,
        retrieval=MemoryRetrieval(cohere_client=None, qdrant_client=QdrantClient(), store=clean_store),
    ),
)

if __name__ == "__main__":
    query = "What is the architecture decision?"
    result = brain.run(query)
    print("Status:", result.status)
    if result.status == "success":
        print("Response:", result.output.response)
        print("Runtime State:\n", result.state)
    else:
        print("Error:", result.error)
