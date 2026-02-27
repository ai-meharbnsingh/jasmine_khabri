"""Pipeline entrypoint — invoked by GitHub Actions via `uv run python -m pipeline.main`."""

import logging
import sys
from datetime import UTC, datetime

from pipeline.utils.loader import load_seen, save_seen
from pipeline.utils.purge import purge_old_entries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)

logger = logging.getLogger(__name__)


def run() -> None:
    """Run the Khabri news pipeline."""
    start = datetime.now(UTC)
    iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.info("=== Khabri pipeline START (%s) ===", iso)

    try:
        # Load state files
        seen = load_seen("data/seen.json")
        history = load_seen("data/history.json")

        # Purge entries older than 7 days
        seen = purge_old_entries(seen, days=7)
        history = purge_old_entries(history, days=7)

        # Save purged state back
        save_seen(seen, "data/seen.json")
        save_seen(history, "data/history.json")

        logger.info(
            "State loaded and purged: seen=%d entries, history=%d entries",
            len(seen.entries),
            len(history.entries),
        )

        # Phase 3-7: fetch, filter, classify, deliver (not yet implemented)
        logger.info("Pipeline phases: not yet implemented (Phase 2 scaffold)")
    except Exception:  # noqa: BLE001
        logger.exception("Pipeline encountered an unhandled error")
        sys.exit(1)
    finally:
        end = datetime.now(UTC)
        elapsed = (end - start).total_seconds()
        logger.info("=== Khabri pipeline END (%.1fs) ===", elapsed)


if __name__ == "__main__":
    run()
