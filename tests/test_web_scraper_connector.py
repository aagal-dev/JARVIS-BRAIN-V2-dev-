from types import SimpleNamespace

from subsystems.research_subsystem.connectors.web_scraper_v3_tavily import (
    WebScraperConnector,
)


def test_web_crawl_records_http_403_as_a_source_failure(monkeypatch) -> None:
    blocked_url = "https://example.org/blocked"
    final_url = "https://example.org/blocked/"
    monkeypatch.setattr(
        "subsystems.research_subsystem.connectors.web_scraper_v3_tavily.fetch_response",
        lambda _url, decode: SimpleNamespace(
            status=403,
            url=final_url,
            html="<html>Access denied</html>",
        ),
    )

    page = WebScraperConnector.web_crawl(
        {"url": blocked_url, "title": "Blocked source"}
    )

    assert page["status"] == "failed"
    assert page["url"] == blocked_url
    assert page["final_url"] == final_url
    assert page["error"] == "HTTP 403"


def test_forbidden_page_does_not_discard_other_research_results(monkeypatch) -> None:
    connector = WebScraperConnector()
    urls = [
        {"url": "https://example.org/blocked", "title": "Blocked"},
        {"url": "https://example.org/usable", "title": "Usable"},
    ]
    monkeypatch.setattr(
        connector,
        "web_search",
        lambda _query: {
            "ok": True,
            "urls": urls,
            "backend": "tavily",
            "errors": [],
        },
    )
    pages = {
        urls[0]["url"]: connector._failed_page(
            urls[0]["url"], urls[0]["url"], "Blocked", "HTTP 403"
        ),
        urls[1]["url"]: {
            "status": "success",
            "url": urls[1]["url"],
            "final_url": urls[1]["url"],
            "title": "Usable",
            "text": "Useful source text.",
            "content_id": "usable-content",
            "quality": {"usable": True},
            "error": None,
        },
    }
    monkeypatch.setattr(
        connector,
        "web_crawl",
        lambda item: pages[item["url"]],
    )

    result = connector.execute("test query")

    assert result["status"] == "partial"
    assert result["summary"]["successful"] == 1
    assert result["summary"]["failed"] == 1
    assert [page["url"] for page in result["results"]] == [urls[1]["url"]]
    assert "HTTP 403" in result["errors"][0]
