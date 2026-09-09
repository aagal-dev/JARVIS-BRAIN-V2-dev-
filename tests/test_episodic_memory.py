import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from agents.conversation_agent import build_conversation_agent_state
from core.agentic_loop import JarvisBrain
from memory.episodic.service import EpisodicMemoryService
from memory.episodic.storage import EpisodicMemoryStore
from schemas.conversation_agent import ConversationAgentOutput
from schemas.episodic_memory import (
    EpisodeRecord,
    EpisodicCreatorResult,
    EpisodicEpisode,
)
from schemas.orchestrator_v2 import ConversationAgentHandoff, OrchestratorResult
from schemas.planner import PlannerResult


TIMESTAMP = datetime(2026, 9, 9, 12, 30, tzinfo=timezone.utc)


def make_episode(summary: str = "The project reached a useful milestone.") -> EpisodicEpisode:
    return EpisodicEpisode(
        type="project",
        summary=summary,
        state="The project was under active development.",
        change="A meaningful project decision was made.",
        outcome="The next implementation direction was clarified.",
        importance=0.8,
        confidence=0.95,
        tags=["project", "development"],
    )


class EpisodicSchemaTests(unittest.TestCase):
    def test_episode_record_lifecycle_rules(self) -> None:
        episode = make_episode()
        create = EpisodeRecord(
            id="episode-001",
            timestamp=TIMESTAMP,
            action="create",
            episode=episode,
        )
        self.assertEqual(create.episode.summary, episode.summary)

        with self.assertRaises(ValueError):
            EpisodeRecord(
                id="episode-002",
                timestamp=TIMESTAMP,
                action="delete",
            )


class EpisodicStorageTests(unittest.TestCase):
    def test_daily_storage_supports_lifecycle_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = EpisodicMemoryStore(Path(directory))
            created = store.create(make_episode(), timestamp=TIMESTAMP)
            updated = store.update(
                created.id,
                make_episode("The milestone was updated with a clearer outcome."),
                timestamp=TIMESTAMP,
            )
            deleted = store.delete(created.id, timestamp=TIMESTAMP)

            path = Path(directory) / "09-9-2026.json"
            self.assertTrue(path.exists())
            records = store.read_day(TIMESTAMP.date())

            self.assertEqual(len(records), 3)
            self.assertEqual(records[0].action, "create")
            self.assertEqual(records[1].target_id, created.id)
            self.assertEqual(records[2].action, "delete")
            self.assertEqual(deleted.target_id, created.id)
            self.assertEqual(updated.episode.summary, "The milestone was updated with a clearer outcome.")

    def test_no_episode_does_not_create_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = EpisodicMemoryService(
                creator=StubCreator(EpisodicCreatorResult()),
                store=EpisodicMemoryStore(Path(directory)),
            )

            result = service.consolidate(
                [{"role": "user", "content": "Hello"}],
                timestamp=TIMESTAMP,
            )

            self.assertFalse(result.created_any)
            self.assertEqual(list(Path(directory).glob("*.json")), [])


class StubCreator:
    def __init__(self, result: EpisodicCreatorResult):
        self.result = result
        self.history = None

    def create(self, chat_history):
        self.history = chat_history
        return self.result


class EpisodicServiceTests(unittest.TestCase):
    def test_service_validates_and_persists_extracted_episodes(self) -> None:
        creator = StubCreator(
            EpisodicCreatorResult(
                should_create=True,
                episodes=[make_episode()],
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            service = EpisodicMemoryService(
                creator=creator,
                store=EpisodicMemoryStore(Path(directory)),
            )
            history = [
                {"role": "user", "content": "We decided to keep the current architecture."},
                {"role": "assistant", "content": "That decision is recorded."},
            ]

            result = service.consolidate(history, timestamp=TIMESTAMP)

            self.assertTrue(result.created_any)
            self.assertEqual(len(result.records), 1)
            self.assertIsNone(result.error)
            self.assertEqual(creator.history, history)


class EpisodicBrainIntegrationTests(unittest.TestCase):
    def test_brain_consolidates_chat_history_only_at_session_end(self) -> None:
        creator = StubCreator(
            EpisodicCreatorResult(
                should_create=True,
                episodes=[make_episode("The session established a durable project decision.")],
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            service = EpisodicMemoryService(
                creator=creator,
                store=EpisodicMemoryStore(Path(directory)),
            )

            def planner(state):
                return PlannerResult(objective="Answer the request")

            def orchestrator(runtime_state, available_components):
                return OrchestratorResult(
                    next_step="respond",
                    conversation_agent_handoff=ConversationAgentHandoff(
                        user_request=runtime_state["user_request"],
                        objective=runtime_state["objective"],
                    ),
                )

            def conversation_agent(state):
                return ConversationAgentOutput(
                    response="A durable answer",
                    response_type="answer",
                )

            brain = JarvisBrain(
                planner=planner,
                orchestrator=orchestrator,
                conversation_agent=conversation_agent,
                episodic_memory=service,
            )

            brain.run("Record this important decision")
            self.assertEqual(len(creator.history or []), 0)

            result = brain.end_session()

            self.assertIsNone(result.error)
            self.assertTrue(result.created_any)
            self.assertEqual(len(creator.history), 2)
            self.assertEqual(brain.chat_history, [])


if __name__ == "__main__":
    unittest.main()