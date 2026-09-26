import os

import httpx
from dotenv import load_dotenv

load_dotenv()


class CohereClientError(RuntimeError):
    """Raised when the Cohere embedding request fails."""


class CohereClient:
    BASE_URL = "https://api.cohere.com/v2/embed"

    def __init__(self, api_key: str | None = None, model: str = "embed-v4.0", output_dimensions: int | None = None):
        self.model = model
        self.output_dimensions = output_dimensions
        self.api_key = api_key or os.getenv("COHERE_API_KEY")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _embed(
        self,
        texts: list[str],
        input_type: str,
    ) -> list[list[float]]:
        if not self.api_key:
            raise CohereClientError(
                "COHERE_API_KEY is not configured; embedding is unavailable."
            )

        payload = {
            "model": self.model,
            "input_type": input_type,
            "texts": texts,
            "embedding_types": ["float"],
        }
        if self.output_dimensions is not None:
            payload["output_dimension"] = self.output_dimensions

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.BASE_URL,
                    headers=self.headers,
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
        except httpx.RequestError as exc:
            raise CohereClientError(f"Network error: {str(exc)}") from exc
        except httpx.HTTPStatusError as exc:
            raise CohereClientError(
                f"HTTP error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except ValueError as exc:
            raise CohereClientError("Cohere returned invalid JSON.") from exc

        if (
            not isinstance(data, dict)
            or not isinstance(data.get("embeddings"), dict)
            or not isinstance(data["embeddings"].get("float"), list)
            or not data["embeddings"]["float"]
        ):
            raise CohereClientError("Unexpected response format from Cohere API.")
        return data["embeddings"]["float"]

    def embed_document(self, text: str) -> list[float]:
        embeddings = self._embed(
            [text],
            input_type="search_document",
        )
        return embeddings[0]

    def embed_query(self, text: str) -> list[float]:
        embeddings = self._embed(
            [text],
            input_type="search_query",
        )
        return embeddings[0]
