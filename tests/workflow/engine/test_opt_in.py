# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The `PICKUP_LABEL` opt-in gate: which issues the orchestrator may enter.

The gate covers the roads a human label opens -- the unlabeled pickup and the
`question` / `discussion` conversations -- and nothing an issue already
carries a workflow stage for. An issue passes only while it wears the opt-in
label and the newest application of that label came from somebody in
`ALLOWED_ISSUE_AUTHORS`; a history that cannot be read admits nobody.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.workflow.engine import opt_in
from orchestrator.workflow.state import WorkflowLabel
from tests.support.fakes import FakeIssueEvent, FakeLabel, FakeUser, make_issue
from tests.workflow.fixtures import _TEST_SPEC

_OPT_IN = "agent-ready"
_ALLOWED = "shukawam"
_OTHER = "teammate"
_LABELED = "labeled"
_UNLABELED = "unlabeled"


def _event(kind: str, label_name: str, login: str) -> FakeIssueEvent:
    return FakeIssueEvent(event=kind, actor=FakeUser(login), label=FakeLabel(label_name))


def _issue(*label_names: str, events: tuple[FakeIssueEvent, ...] = ()):
    issue = make_issue(1)
    issue.labels = [FakeLabel(label_name) for label_name in label_names]
    issue.events = list(events)
    return issue


class _GateMixin:
    def setUp(self) -> None:
        patches = (
            patch.object(config, "PICKUP_LABEL", _OPT_IN),
            patch.object(config, "ALLOWED_ISSUE_AUTHORS", (_ALLOWED,)),
        )
        for active in patches:
            active.start()
            self.addCleanup(active.stop)


class OptInDisabledTest(unittest.TestCase):
    def test_disabled_never_refuses(self) -> None:
        with patch.object(config, "PICKUP_LABEL", ""):
            self.assertFalse(opt_in._opt_in_refuses(_TEST_SPEC, _issue(), None))


class OptInPickupTest(_GateMixin, unittest.TestCase):
    def test_unlabeled_without_label_is_refused(self) -> None:
        self.assertTrue(opt_in._opt_in_refuses(_TEST_SPEC, _issue(), None))

    def test_label_from_allowed_user_is_admitted(self) -> None:
        issue = _issue(_OPT_IN, events=(_event(_LABELED, _OPT_IN, _ALLOWED),))
        self.assertFalse(opt_in._opt_in_refuses(_TEST_SPEC, issue, None))

    def test_label_from_other_user_is_refused(self) -> None:
        issue = _issue(_OPT_IN, events=(_event(_LABELED, _OPT_IN, _OTHER),))
        self.assertTrue(opt_in._opt_in_refuses(_TEST_SPEC, issue, None))

    def test_label_and_login_match_case_insensitively(self) -> None:
        issue = _issue("Agent-Ready", events=(_event(_LABELED, "Agent-Ready", "ShuKawam"),))
        self.assertFalse(opt_in._opt_in_refuses(_TEST_SPEC, issue, None))

    def test_newest_application_decides(self) -> None:
        readmitted = _issue(_OPT_IN, events=(
            _event(_LABELED, _OPT_IN, _OTHER),
            _event(_UNLABELED, _OPT_IN, _OTHER),
            _event(_LABELED, _OPT_IN, _ALLOWED),
        ))
        overtaken = _issue(_OPT_IN, events=(
            _event(_LABELED, _OPT_IN, _ALLOWED),
            _event(_UNLABELED, _OPT_IN, _ALLOWED),
            _event(_LABELED, _OPT_IN, _OTHER),
        ))
        self.assertFalse(opt_in._opt_in_refuses(_TEST_SPEC, readmitted, None))
        self.assertTrue(opt_in._opt_in_refuses(_TEST_SPEC, overtaken, None))

    def test_unreadable_history_is_refused(self) -> None:
        issue = _issue(_OPT_IN)
        with patch.object(issue, "get_events", side_effect=RuntimeError("events unavailable")):
            self.assertTrue(opt_in._opt_in_refuses(_TEST_SPEC, issue, None))


class OptInStageTest(_GateMixin, unittest.TestCase):
    def test_question_and_discussion_are_gated(self) -> None:
        for stage in (WorkflowLabel.QUESTION, WorkflowLabel.DISCUSSION):
            with self.subTest(stage=stage):
                bare = _issue(str(stage))
                opted = _issue(
                    str(stage), _OPT_IN, events=(_event(_LABELED, _OPT_IN, _ALLOWED),),
                )
                self.assertTrue(opt_in._opt_in_refuses(_TEST_SPEC, bare, stage))
                self.assertFalse(opt_in._opt_in_refuses(_TEST_SPEC, opted, stage))

    def test_inflight_stage_is_never_gated(self) -> None:
        issue = _issue(str(WorkflowLabel.IMPLEMENTING))
        self.assertFalse(
            opt_in._opt_in_refuses(_TEST_SPEC, issue, WorkflowLabel.IMPLEMENTING),
        )
