import sys
import json
from core.agentic_loop import JarvisBrain
from core.registry.available_components import AVAILABLE_COMPONENTS
from agents.planner import run_planner, build_planner_state
from agents.conversation_agent import run_conversation_agent, build_conversation_agent_state
from core.orchestrator import run_orchestrator
from memory.episodic.service import EpisodicMemoryService
from memory.episodic.storage import EpisodicMemoryStore
from memory.retrieval import MemoryRetrieval
from integrations.qdrant_client import QdrantClient
from integrations.voyage_client import VoyageClient
import tempfile
from pathlib import Path

def test_workflow(user_request):
    print(f"\n--- Testing Request: {user_request} ---")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup minimal infrastructure
        store = EpisodicMemoryStore(Path(tmpdir))
        # Use mock-like clients or real ones if configured. 
        # For a pure logic test, we assume they are initialized via settings or mocked.
        # Here we just instantiate to check if the loop runs.
        try:
            voyage = VoyageClient(api_key="test") 
            qdrant = QdrantClient(url="http://localhost:6333")
            retrieval = MemoryRetrieval(voyage_client=voyage, qdrant_client=qdrant, store=store)
            service = EpisodicMemoryService(
                creator=None, # We can mock the creator
                store=store,
                retrieval=retrieval
            )
            
            brain = JarvisBrain(
                planner=run_planner,
                orchestrator=run_orchestrator,
                conversation_agent=run_conversation_agent,
                episodic_memory=service,
                memory_retrieval=retrieval
            )
            
            result = brain.run(user_request)
            print(f"Result Status: {result.status}")
            if result.error:
                print(f"Error: {result.error}")
            else:
                print(f"Response: {result.output.response if result.output else 'No output'}")
            return result
        except Exception as e:
            print(f"Runtime Crash: {e}")
            return None

if __name__ == "__main__":
    test_cases = [
        "Hello Jarvis, who are you?",
        "I want to start a new project called 'Omega'. Please remember this.",
        "What did we decide about project Omega?",
    ]
    
    for tc in test_cases:
        test_workflow(tc)
