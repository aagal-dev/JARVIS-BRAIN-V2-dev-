import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from schemas.episodic_memory import EpisodeRecord, EpisodicEpisode


class EpisodicMemoryStore:
    """Persists lifecycle records as one JSON list per calendar day."""

    def __init__(self, episodes_dir: Path | str = "memory/episodic/episodes"):
        self.episodes_dir = Path(episodes_dir)

    def create(
        self,
        episode: EpisodicEpisode,
        timestamp: datetime | None = None,
    ) -> EpisodeRecord:
        record = EpisodeRecord(
            id=str(uuid4()),
            timestamp=timestamp or datetime.now(timezone.utc),
            action="create",
            episode=episode,
        )
        self._append(record)
        return record

    def update(
        self,
        target_id: str,
        episode: EpisodicEpisode,
        timestamp: datetime | None = None,
    ) -> EpisodeRecord:
        record = EpisodeRecord(
            id=str(uuid4()),
            timestamp=timestamp or datetime.now(timezone.utc),
            action="update",
            target_id=target_id,
            episode=episode,
        )
        self._append(record)
        return record

    def delete(
        self,
        target_id: str,
        timestamp: datetime | None = None,
    ) -> EpisodeRecord:
        record = EpisodeRecord(
            id=str(uuid4()),
            timestamp=timestamp or datetime.now(timezone.utc),
            action="delete",
            target_id=target_id,
        )
        self._append(record)
        return record

    def read_day(self, day: date) -> list[EpisodeRecord]:
        path = self._path_for_day(day)
        if not path.exists():
            return []

        try:
            raw_records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not read episodic memory file: {path}") from exc

        if not isinstance(raw_records, list):
            raise RuntimeError(f"Episodic memory file must contain a JSON list: {path}")

        return [EpisodeRecord.model_validate(record) for record in raw_records]

    def list_active(self) -> list[EpisodeRecord]:
        """Return the current canonical episode state across all daily files."""
        records: list[EpisodeRecord] = []
        if not self.episodes_dir.exists():
            return []

        for path in sorted(self.episodes_dir.glob("*.json")):
            try:
                raw_records = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"Could not read episodic memory file: {path}"
                ) from exc
            if not isinstance(raw_records, list):
                raise RuntimeError(
                    f"Episodic memory file must contain a JSON list: {path}"
                )
            records.extend(
                EpisodeRecord.model_validate(record) for record in raw_records
            )

        active: dict[str, EpisodeRecord] = {}
        for record in sorted(records, key=lambda item: item.timestamp):
            if record.action == "create" and record.episode is not None:
                active[record.id] = record
            elif record.action == "update" and record.target_id:
                original = active.get(record.target_id)
                if original is not None and record.episode is not None:
                    active[record.target_id] = original.model_copy(
                        update={"episode": record.episode}
                    )
            elif record.action == "delete" and record.target_id:
                active.pop(record.target_id, None)

        return list(active.values())

    def get_active_by_ids(self, ids: list[str]) -> dict[str, EpisodeRecord]:
        wanted = set(ids)
        return {
            record.id: record
            for record in self.list_active()
            if record.id in wanted
        }

    def _append(self, record: EpisodeRecord) -> None:
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        existing = self.read_day(record.timestamp.date())
        existing.append(record)
        payload = [item.model_dump(mode="json") for item in existing]
        path = self._path_for_day(record.timestamp.date())

        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.episodes_dir,
                delete=False,
            ) as temporary:
                json.dump(payload, temporary, indent=2)
                temporary.write("\n")
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, path)
        except OSError as exc:
            if "temporary_path" in locals():
                temporary_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Could not persist episodic memory file: {path}"
            ) from exc

    def _path_for_day(self, day: date) -> Path:
        filename = f"{day.day:02d}-{day.month}-{day.year}.json"
        return self.episodes_dir / filename