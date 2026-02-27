"""Pipeline entrypoint — invoked by GitHub Actions via `uv run python -m pipeline.main`."""

import logging
import sys
from datetime import UTC, datetime

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
        # Phase 2: stub — phases 3-7 will add fetch/filter/deliver calls here
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
