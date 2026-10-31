# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""How loudly the `PICKUP_LABEL` gate reports a refusal.

A missing opt-in label is the steady state of most open issues and recurs on
every poll, so it is a DEBUG line. A label applied by somebody outside
`ALLOWED_ISSUE_AUTHORS` is rare and worth an operator's eye, so it stays INFO.
"""
from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.workflow.engine import opt_in
from tests.support.fakes import FakeIssueEvent, FakeLabel, FakeUser, make_issue
from tests.workflow.fixtures import _TEST_SPEC

_OPT_IN = "agent-ready"


def _issue(*label_names: str, events: tuple[FakeIssueEvent, ...] = ()):
    issue = make_issue(1)
    issue.labels = [FakeLabel(label_name) for label_name in label_names]
    issue.events = list(events)
    return issue


class RefusalLogLevelTest(unittest.TestCase):
    def setUp(self) -> None:
        patches = (
            patch.object(config, "PICKUP_LABEL", _OPT_IN),
            patch.object(config, "ALLOWED_ISSUE_AUTHORS", ("shukawam",)),
        )
        for active in patches:
            active.start()
            self.addCleanup(active.stop)

    def test_missing_label_logs_at_debug(self) -> None:
        self.assertEqual(self._refusal_level(_issue()), logging.DEBUG)

    def test_foreign_labeler_logs_at_info(self) -> None:
        labeled = FakeIssueEvent(
            event="labeled", actor=FakeUser("teammate"), label=FakeLabel(_OPT_IN),
        )
        issue = _issue(_OPT_IN, events=(labeled,))
        self.assertEqual(self._refusal_level(issue), logging.INFO)

    def _refusal_level(self, issue) -> int:
        with self.assertLogs("orchestrator.workflow", level=logging.DEBUG) as captured:
            self.assertTrue(opt_in._opt_in_refuses(_TEST_SPEC, issue, None))
            first_level = captured.records[0].levelno
        return first_level


if __name__ == "__main__":
    unittest.main()
