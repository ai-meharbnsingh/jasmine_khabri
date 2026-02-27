"""News source fetchers (RSS, GNews API)."""

from pipeline.fetchers.rss_fetcher import fetch_all_rss, fetch_rss_feed

__all__ = ["fetch_all_rss", "fetch_rss_feed"]
