import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.agentic_loop import JarvisBrain
from integrations.qdrant_client import QdrantClient
from integrations.voyage_client import VoyageClient
from memory.episodic.service import EpisodicMemoryService
from memory.episodic.storage import EpisodicMemoryStore
from memory.retrieval import MemoryRetrieval
from schemas.agents.conversation_agent import ConversationAgentOutput
from schemas.agents.planner import PlannerResult
from schemas.episodic_memory import (
    EpisodeRecord,
    EpisodicCreatorResult,
    EpisodicEpisode,
)
from schemas.memory_retrieval import (
    MemoryRetrievalResult,
    MemoryRetrievalResultItem,
)
from schemas.orchestrator.orchestrator_v2 import (
    ConversationAgentHandoff,
    OrchestratorResult,
)


TIMESTAMP = datetime(2026, 9, 9, 12, 30, tzinfo=timezone.utc)


def make_episode(summary: str) -> EpisodicEpisode:
    return EpisodicEpisode(
        type="project",
        summary=summary,
        state="The project was active.",
        change="A durable decision was recorded.",
        outcome="Future work can use the decision.",
        importance=0.8,
        confidence=0.9,
        tags=["project"],
    )


class FakeVoyage:
    def __init__(self, query_vector=None, document_vector=None, error=None):
        self.query_vector = query_vector or [0.1, 0.2]
        self.document_vector = document_vector or [0.3, 0.4]
        self.error = error
        self.queries = []
        self.documents = []

    def embed_query(self, text):
        if self.error:
            raise RuntimeError(self.error)
        self.queries.append(text)
        return self.query_vector

    def embed_document(self, text):
        if self.error:
            raise RuntimeError(self.error)
        self.documents.append(text)
        return self.document_vector


class FakeQdrant:
    def __init__(self, points=None, error=None):
        self.points = points or []
        self.error = error
        self.hybrid_queries = []
        self.upserts = []
        self.deletes = []

    def hybrid_search(self, **kwargs):
        if self.error:
            raise RuntimeError(self.error)
        self.hybrid_queries.append(kwargs)
        return self.points

    def upsert_episode(self, **kwargs):
        if self.error:
            raise RuntimeError(self.error)
        self.upserts.append(kwargs)

    def delete_episode(self, episode_id):
        self.deletes.append(episode_id)


class StubCreator:
    def __init__(self, episodes):
        self.episodes = episodes

    def create(self, chat_history):
        return EpisodicCreatorResult(
            should_create=bool(self.episodes),
            episodes=self.episodes,
        )


class MemoryRetrievalTests(unittest.TestCase):
    def test_hybrid_results_map_back_to_canonical_episodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = EpisodicMemoryStore(Path(directory))
            record = store.create(
                make_episode("The architecture decision is important."),
                timestamp=TIMESTAMP,
            )
            voyage = FakeVoyage()
            qdrant = FakeQdrant(
                points=[
                    {
                        "id": record.id,
                        "score": 0.91,
                        "payload": {
                            "episode_id": record.id,
                            "summary": "A stale or abbreviated payload",
                        },
                    }
                ]
            )
            retrieval = MemoryRetrieval(
                voyage_client=voyage,
                qdrant_client=qdrant,
                store=store,
            )

            result = retrieval.retrieve("What architecture decision did we make?")

            self.assertIsNone(result.error)
            self.assertEqual(len(result.results), 1)
            self.assertEqual(
                result.results[0].episode.summary,
                "The architecture decision is important.",
            )
            self.assertEqual(qdrant.hybrid_queries[0]["query"], result.query)
            self.assertEqual(voyage.queries, [result.query])

    def test_retrieval_errors_are_explicit_and_do_not_fabricate_results(self) -> None:
        retrieval = MemoryRetrieval(
            voyage_client=FakeVoyage(error="Voyage unavailable"),
            qdrant_client=FakeQdrant(),
            store=EpisodicMemoryStore(tempfile.mkdtemp()),
        )

        result = retrieval.retrieve("Find the earlier decision")

        self.assertEqual(result.results, [])
        self.assertIn("Voyage unavailable", result.error)

    def test_rebuild_uses_current_canonical_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = EpisodicMemoryStore(Path(directory))
            first = store.create(
                make_episode("Original summary"),
                timestamp=TIMESTAMP,
            )
            second = store.create(
                make_episode("This episode will be deleted"),
                timestamp=TIMESTAMP,
            )
            store.update(
                first.id,
                make_episode("Updated canonical summary"),
                timestamp=TIMESTAMP,
            )
            store.delete(second.id, timestamp=TIMESTAMP)

            voyage = FakeVoyage()
            qdrant = FakeQdrant()
            retrieval = MemoryRetrieval(voyage, qdrant, store)

            errors = retrieval.rebuild_index()

            self.assertEqual(errors, [])
            self.assertEqual(
                [item["episode_id"] for item in qdrant.upserts],
                [first.id],
            )
            self.assertEqual(
                qdrant.upserts[0]["summary"],
                "Updated canonical summary",
            )


class EpisodicIndexingBoundaryTests(unittest.TestCase):
    def test_canonical_episode_survives_indexing_failure(self) -> None:
        class FailingRetrieval:
            def __init__(self, store):
                self.store = store
                self.seen_after_persist = False

            def index_record(self, record):
                self.seen_after_persist = bool(
                    self.store.get_active_by_ids([record.id])
                )
                return "Qdrant is unavailable"

        with tempfile.TemporaryDirectory() as directory:
            store = EpisodicMemoryStore(Path(directory))
            retrieval = FailingRetrieval(store)
            service = EpisodicMemoryService(
                creator=StubCreator([make_episode("Keep this canonical record")]),
                store=store,
                retrieval=retrieval,
            )

            result = service.consolidate(
                [{"role": "user", "content": "Remember this"}],
                timestamp=TIMESTAMP,
            )

            self.assertIsNone(result.error)
            self.assertTrue(retrieval.seen_after_persist)
            self.assertEqual(len(result.records), 1)
            self.assertEqual(len(result.indexing_errors), 1)
            self.assertEqual(len(store.list_active()), 1)


class RetrievalWorkflowTests(unittest.TestCase):
    def test_retrieval_context_reaches_planner_and_conversation_agent(self) -> None:
        episode = make_episode("The user prefers the existing architecture.")
        retrieval_result = MemoryRetrievalResult(
            query="architecture preference",
            results=[
                MemoryRetrievalResultItem(
                    id="episode-1",
                    score=0.88,
                    episode=episode,
                )
            ],
        )

        class StubRetrieval:
            def retrieve(self, query):
                return retrieval_result

            def index_record(self, record):
                return None

        planner_states = []
        conversation_states = []

        def planner(state):
            planner_states.append(state)
            return PlannerResult(objective="Answer with relevant prior context")

        def orchestrator(runtime_state, available_components):
            return OrchestratorResult(
                next_step="respond",
                conversation_agent_handoff=ConversationAgentHandoff(
                    user_request=runtime_state["user_request"],
                    objective=runtime_state["objective"],
                ),
            )

        def conversation_agent(state):
            conversation_states.append(state)
            return ConversationAgentOutput(
                response="Grounded response",
                response_type="answer",
            )

        with tempfile.TemporaryDirectory() as directory:
            store = EpisodicMemoryStore(Path(directory))
            service = EpisodicMemoryService(
                creator=StubCreator([]),
                store=store,
                retrieval=StubRetrieval(),
            )
            brain = JarvisBrain(
                planner=planner,
                orchestrator=orchestrator,
                conversation_agent=conversation_agent,
                episodic_memory=service,
                memory_retrieval=service.retrieval,
            )

            result = brain.run("What architecture should we keep?")

        self.assertEqual(result.status, "success")
        self.assertEqual(
            planner_states[0]["relevant_context"]["episodic_memory"][0]["summary"],
            episode.summary,
        )
        self.assertEqual(
            conversation_states[0]["relevant_context"]["episodic_memory"][0]["id"],
            "episode-1",
        )


class HttpBoundaryTests(unittest.TestCase):
    def test_voyage_client_parses_embeddings_and_sends_model(self) -> None:
        requests = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "data": [
                            {"index": 0, "embedding": [0.1, 0.2]},
                            {"index": 1, "embedding": [0.3, 0.4]},
                        ]
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return Response()

        with patch("integrations.voyage_client.urlopen", fake_urlopen):
            client = VoyageClient(api_key="test-key", max_retries=0)
            vectors = client.embed(["one", "two"], input_type="document")

        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])
        self.assertIn("voyage-4-lite", requests[0][0].data.decode("utf-8"))
        self.assertEqual(
            requests[0][0].headers["Authorization"],
            "Bearer test-key",
        )

    def test_qdrant_hybrid_request_contains_dense_sparse_rrf(self) -> None:
        requests = []
        client = QdrantClient(url="https://qdrant.test", max_retries=0)

        def fake_request(method, path, payload=None):
            requests.append((method, path, payload))
            if method == "GET":
                return {}
            return {"result": {"points": []}}

        client._request = fake_request
        client.hybrid_search(
            query="exact project identifier",
            dense_vector=[0.1, 0.2],
            limit=4,
        )

        body = requests[-1][2]
        self.assertEqual(body["query"], {"fusion": "rrf"})
        self.assertEqual(len(body["prefetch"]), 2)
        self.assertEqual(body["prefetch"][0]["using"], "dense")
        self.assertEqual(body["prefetch"][1]["using"], "text")
        self.assertEqual(
            body["prefetch"][1]["query"]["model"],
            "Qdrant/bm25",
        )


if __name__ == "__main__":
    unittest.main()