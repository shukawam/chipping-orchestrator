# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""`STDERR_LOG_LEVEL` thins stderr only while the rotating file keeps every line."""

from __future__ import annotations

import logging
import unittest
from unittest.mock import Mock, patch

from orchestrator import config
from orchestrator.runtime import logs

_STDERR_LEVEL_ATTR = "STDERR_LOG_LEVEL"
_WARNING = "WARNING"


class StderrLevelTest(unittest.TestCase):
    def test_level_applies_beside_the_file(self) -> None:
        installed = self._installed(_WARNING, Mock(return_value=logging.NullHandler()))
        self.assertEqual(installed[0].level, logging.WARNING)

    def test_unset_level_keeps_every_line(self) -> None:
        installed = self._installed("", Mock(return_value=logging.NullHandler()))
        self.assertEqual(installed[0].level, logging.NOTSET)

    def test_level_ignored_without_the_file(self) -> None:
        failing = Mock(side_effect=OSError("read-only file system"))
        with self.assertLogs("orchestrator", level=logging.WARNING):
            installed = self._installed(_WARNING, failing)
        self.assertEqual(installed[0].level, logging.NOTSET)

    def _installed(self, stderr_level: str, file_handler: Mock) -> list[logging.Handler]:
        with (
            patch.object(config, _STDERR_LEVEL_ATTR, stderr_level),
            patch.object(logs, "rotating_file_handler", file_handler),
            patch.object(logging, "basicConfig") as configured,
        ):
            logs.configure_logging("INFO")
            installed = configured.call_args.kwargs["handlers"]
        return installed


if __name__ == "__main__":
    unittest.main()
