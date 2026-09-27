from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..configs.settings import PROMPTS_DIR
from ..integrations.ollama_llm import OllamaModel

with (PROMPTS_DIR / "summarizer_prompt.txt").open(
    "r",
    encoding="utf-8",
) as file:
  summarizer_prompt = file.read()

class LLMForSummarization:
    def __init__(self):
        self.model = OllamaModel()

    def summarize(self, text: str) -> str:
        result = self.model.call_model(
            state=text,
            system_ins=summarizer_prompt,
        )

        if isinstance(result, dict):
            return str(result.get("summary", "")).strip()

        raise ValueError(
            f"Unexpected model response: {type(result).__name__}"
        )


class ConnectorContentNormalizer:
    """
    Extract useful textual content from flat or deeply nested
    connector results while ignoring metadata/failures.
    """

    CONTENT_KEYS = {
        "text",
        "content",
        "transcript",
        "transcription",
        "description",
        "summary",
        "abstract",
        "web_scraped_text",
    }

    CONTAINER_KEYS = {
        "results",
        "pages",
        "items",
        "documents",
        "data",
        "sources",
    }

    META_KEYS = {
        "title",
        "url",
        "final_url",
        "source",
        "source_url",
        "connector_name",
        "query",
        "status",
        "content_type",
        "quality",
        "evidence",
        "document_id",
        "content_id",
        "extraction",
        "error",
        "score",
        "domain",
        "type",
        "tier",
        "heuristic",
        "year",
        "authors",
    }

    def normalize(self, results: Any) -> list[str]:
        found: list[str] = []
        self._walk(results, found)

        # Remove exact/near-exact duplicate content while preserving order.
        unique = []
        seen = set()

        for text in found:
            key = " ".join(text.split()).lower()

            if len(key) < 30 or key in seen:
                continue

            seen.add(key)
            unique.append(text.strip())

        return unique

    def _walk(self, value: Any, output: list[str]) -> None:
        if isinstance(value, str):
            return

        if isinstance(value, list):
            for item in value:
                self._walk(item, output)
            return

        if not isinstance(value, dict):
            return

        # Ignore failed connector documents.
        if value.get("status") == "failed":
            return

        # Ignore explicitly unusable documents.
        quality = value.get("quality")
        if isinstance(quality, dict) and quality.get("usable") is False:
            return

        # Extract known content-bearing fields first.
        for key in self.CONTENT_KEYS:
            if key not in value:
                continue

            content = value[key]

            if isinstance(content, str) and content.strip():
                output.append(content)
            else:
                self._walk(content, output)

        # Traverse nested connector containers.
        for key in self.CONTAINER_KEYS:
            if key in value:
                self._walk(value[key], output)

        # Generic fallback for unknown nested structures.
        for key, child in value.items():
            if key in (
                self.CONTENT_KEYS
                | self.CONTAINER_KEYS
                | self.META_KEYS
            ):
                continue

            if isinstance(child, (dict, list)):
                self._walk(child, output)


@dataclass
class SummaryNode:
    text: str
    level: int


class TreeSummarizer:
    """
    Clean public pipeline:

        final_summary = TreeSummarizer().run(results)
    """

    def __init__(
        self,
        llm: LLMForSummarization | None = None,
        chunk_size: int = 1200,
        group_size: int = 3,
    ):
        self.llm = llm or LLMForSummarization()
        self.normalizer = ConnectorContentNormalizer()
        self.chunk_size = chunk_size
        self.group_size = group_size

    def run(self, normalized_connector_results: Any) -> str:
        contents = self.normalizer.normalize(
            normalized_connector_results
        )

        if not contents:
            return ""

        chunks = self._create_chunks(contents)

        nodes = [
            SummaryNode(text=chunk, level=0)
            for chunk in chunks
        ]

        while len(nodes) > 1:
            nodes = self._summarize_window(nodes)

        return nodes[0].text if nodes else ""

    def _create_chunks(self, contents: list[str]) -> list[str]:
        chunks = []

        for content in contents:
            words = content.split()

            for i in range(0, len(words), self.chunk_size):
                chunk = " ".join(
                    words[i:i + self.chunk_size]
                ).strip()

                if chunk:
                    chunks.append(chunk)

        return chunks

    def _summarize_window(
        self,
        nodes: list[SummaryNode],
    ) -> list[SummaryNode]:

        next_level = nodes[0].level + 1
        output = []

        for i in range(0, len(nodes), self.group_size):
            window = nodes[i:i + self.group_size]

            combined = "\n\n".join(
                node.text for node in window
            )

            summary = self.llm.summarize(combined)

            if summary:
                output.append(
                    SummaryNode(
                        text=summary,
                        level=next_level,
                    )
                )

        return output