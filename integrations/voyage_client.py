import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class VoyageClientError(RuntimeError):
    """Raised when the Voyage embedding boundary cannot complete a request."""


class VoyageClient:
    """Small HTTP-only client for Voyage embeddings."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "voyage-4-lite",
        base_url: str | None = None,
        timeout: float = 20.0,
        max_retries: int = 1,
        retry_delay: float = 0.2,
    ) -> None:
        self.api_key = api_key or os.getenv("VOYAGE_API_KEY")
        self.model = model
        self.base_url = (base_url or os.getenv(
            "VOYAGE_API_URL", "https://api.voyageai.com/v1"
        )).rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.retry_delay = max(0.0, retry_delay)

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text], input_type="query")[0]

    def embed_document(self, text: str) -> list[float]:
        return self.embed([text], input_type="document")[0]

    def embed(
        self,
        texts: list[str],
        input_type: str,
    ) -> list[list[float]]:
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise VoyageClientError("Voyage embedding input must contain non-empty text.")
        if input_type not in {"query", "document"}:
            raise VoyageClientError(
                f"Unsupported Voyage input_type: {input_type}"
            )
        if not self.api_key:
            raise VoyageClientError(
                "VOYAGE_API_KEY is not configured; memory retrieval is unavailable."
            )

        payload = {
            "input": texts,
            "model": self.model,
            "input_type": input_type,
        }
        response = self._request("POST", "/embeddings", payload)
        data = response.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise VoyageClientError(
                "Voyage returned an invalid embedding response."
            )

        ordered: list[list[float] | None] = [None] * len(texts)
        for item in data:
            if not isinstance(item, dict):
                raise VoyageClientError(
                    "Voyage returned an invalid embedding item."
                )
            index = item.get("index")
            embedding = item.get("embedding")
            if not isinstance(index, int) or not 0 <= index < len(texts):
                raise VoyageClientError(
                    "Voyage returned an invalid embedding index."
                )
            if (
                not isinstance(embedding, list)
                or not embedding
                or any(not isinstance(value, (int, float)) for value in embedding)
            ):
                raise VoyageClientError(
                    "Voyage returned an invalid embedding vector."
                )
            ordered[index] = [float(value) for value in embedding]

        if any(vector is None for vector in ordered):
            raise VoyageClientError(
                "Voyage returned incomplete embedding data."
            )
        return [vector for vector in ordered if vector is not None]

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise VoyageClientError(
                        "Voyage returned a non-object JSON response."
                    )
                return parsed
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                raise VoyageClientError(
                    f"Voyage HTTP {exc.code}: {body[:500]}"
                ) from exc
            except (URLError, TimeoutError) as exc:
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                raise VoyageClientError(
                    f"Voyage network failure: {str(exc)[:500]}"
                ) from exc
            except json.JSONDecodeError as exc:
                raise VoyageClientError(
                    "Voyage returned invalid JSON."
                ) from exc