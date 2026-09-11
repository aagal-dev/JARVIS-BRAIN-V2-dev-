import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

class QdrantClientError(RuntimeError):
    """Raised when the Qdrant retrieval boundary cannot complete a request."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class QdrantClient:
    """Small HTTP-only client for Qdrant collection, indexing, and search."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection: str | None = None,
        dense_vector_name: str = "dense",
        sparse_vector_name: str = "text",
        sparse_model: str = "Qdrant/bm25",
        timeout: float = 20.0,
        max_retries: int = 1,
        retry_delay: float = 0.2,
    ) -> None:
        self.url = (url or os.getenv("QDRANT_URL") or "").rstrip("/")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.collection = collection or os.getenv(
            "QDRANT_COLLECTION", "jarvis_episodic_memory"
        )
        self.dense_vector_name = dense_vector_name
        self.sparse_vector_name = sparse_vector_name
        self.sparse_model = sparse_model
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.retry_delay = max(0.0, retry_delay)

    def ensure_collection(self, dense_size: int) -> None:
        if not self.url:
            raise QdrantClientError(
                "QDRANT_URL is not configured; memory retrieval is unavailable."
            )
        if dense_size <= 0:
            raise QdrantClientError("Qdrant dense vector size must be positive.")

        try:
            self._request(
                "GET",
                f"/collections/{quote(self.collection, safe='')}",
            )
            return
        except QdrantClientError as exc:
            if exc.status_code != 404:
                raise

        self._request(
            "PUT",
            f"/collections/{quote(self.collection, safe='')}",
            {
                "vectors": {
                    self.dense_vector_name: {
                        "size": dense_size,
                        "distance": "Cosine",
                    }
                },
                "sparse_vectors": {
                    self.sparse_vector_name: {
                        "modifier": "idf",
                    }
                },
            },
        )

    def upsert_episode(
        self,
        episode_id: str,
        summary: str,
        dense_vector: list[float],
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.ensure_collection(len(dense_vector))
        point_payload = {
            "episode_id": episode_id,
            "summary": summary,
            **(payload or {}),
        }
        self._request(
            "PUT",
            f"/collections/{quote(self.collection, safe='')}/points?wait=true",
            {
                "points": [
                    {
                        "id": episode_id,
                        "vector": {
                            self.dense_vector_name: dense_vector,
                            self.sparse_vector_name: {
                                "text": summary,
                                "model": self.sparse_model,
                            },
                        },
                        "payload": point_payload,
                    }
                ]
            },
        )

    def delete_episode(self, episode_id: str) -> None:
        self._ensure_configured()
        self._request(
            "POST",
            f"/collections/{quote(self.collection, safe='')}/points/delete?wait=true",
            {"points": [episode_id]},
        )

    def dense_search(
        self,
        dense_vector: list[float],
        limit: int,
        query_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection(len(dense_vector))
        response = self._request(
            "POST",
            f"/collections/{quote(self.collection, safe='')}/points/query",
            {
                "query": dense_vector,
                "using": self.dense_vector_name,
                "limit": limit,
                "with_payload": True,
                **({"filter": query_filter} if query_filter else {}),
            },
        )
        return self._points(response)

    def sparse_search(
        self,
        query: str,
        limit: int,
        query_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_configured()
        response = self._request(
            "POST",
            f"/collections/{quote(self.collection, safe='')}/points/query",
            {
                "query": {
                    "text": query,
                    "model": self.sparse_model,
                },
                "using": self.sparse_vector_name,
                "limit": limit,
                "with_payload": True,
                **({"filter": query_filter} if query_filter else {}),
            },
        )
        return self._points(response)

    def hybrid_search(
        self,
        query: str,
        dense_vector: list[float],
        limit: int,
        query_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection(len(dense_vector))
        prefetch_limit = max(limit * 3, limit)
        response = self._request(
            "POST",
            f"/collections/{quote(self.collection, safe='')}/points/query",
            {
                "prefetch": [
                    {
                        "query": dense_vector,
                        "using": self.dense_vector_name,
                        "limit": prefetch_limit,
                    },
                    {
                        "query": {
                            "text": query,
                            "model": self.sparse_model,
                        },
                        "using": self.sparse_vector_name,
                        "limit": prefetch_limit,
                    },
                ],
                "query": {"fusion": "rrf"},
                "limit": limit,
                "with_payload": True,
                **({"filter": query_filter} if query_filter else {}),
            },
        )
        return self._points(response)

    def _ensure_configured(self) -> None:
        if not self.url:
            raise QdrantClientError(
                "QDRANT_URL is not configured; memory retrieval is unavailable."
            )

    def _points(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        result = response.get("result")
        if isinstance(result, dict):
            result = result.get("points")
        if not isinstance(result, list):
            raise QdrantClientError("Qdrant returned an invalid points response.")
        return [point for point in result if isinstance(point, dict)]

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_configured()
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["api-key"] = self.api_key

        request = Request(
            f"{self.url}{path}",
            data=data,
            method=method,
            headers=headers,
        )
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                parsed = json.loads(raw) if raw else {}
                if not isinstance(parsed, dict):
                    raise QdrantClientError(
                        "Qdrant returned a non-object JSON response."
                    )
                return parsed
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                raise QdrantClientError(
                    f"Qdrant HTTP {exc.code}: {body[:500]}",
                    status_code=exc.code,
                ) from exc
            except (URLError, TimeoutError) as exc:
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                raise QdrantClientError(
                    f"Qdrant network failure: {str(exc)[:500]}"
                ) from exc
            except json.JSONDecodeError as exc:
                raise QdrantClientError(
                    "Qdrant returned invalid JSON."
                ) from exc