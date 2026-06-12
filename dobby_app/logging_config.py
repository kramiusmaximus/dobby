from __future__ import annotations

import logging

from dobby_app.config import settings


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.DEBUG)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )
