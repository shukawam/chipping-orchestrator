# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The `STDERR_LOG_LEVEL` name check, split from the resolver in `environment`
so that module stays within its member budget."""
from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn

# The level names `STDERR_LOG_LEVEL` accepts: the ones `logging` itself knows.
_LOG_LEVEL_NAMES = frozenset(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))


def parse_stderr_log_level(
    raw_level: str, config_error: Callable[[str], NoReturn],
) -> str:
    """Normalize a `STDERR_LOG_LEVEL` name; empty means stderr keeps every line."""
    level_name = raw_level.strip().upper()
    if level_name and level_name not in _LOG_LEVEL_NAMES:
        config_error(
            f"orchestrator: STDERR_LOG_LEVEL={raw_level!r} is not a log level; "
            "expected DEBUG, INFO, WARNING, ERROR, or CRITICAL",
        )
    return level_name
