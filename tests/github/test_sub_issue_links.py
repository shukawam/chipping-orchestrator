# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""`CHILD_AS_SUB_ISSUE`: a split's children become sub-issues of their parent.

The link and the assignee are bookkeeping on top of a child that already
exists, so neither may cost the split its child: an already-linked child is
success, and any other failure is logged and swallowed.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from github import GithubException

from orchestrator import config
from orchestrator.github.client import GitHubClient
from tests.support.fakes import FakeIssueEvent, FakeLabel, FakeUser

_PARENT_NUMBER = 40
_CHILD_ID = 901
_OWNER = "shukawam"
_OPT_IN = "agent-ready"
_CHILD_SWITCH = "CHILD_AS_SUB_ISSUE"
_ALREADY_LINKED = 422
_SERVER_ERROR = 500


class SubIssueLinkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GitHubClient.__new__(GitHubClient)
        self.client.repo = MagicMock()
        self.parent = MagicMock(assignees=[FakeUser(_OWNER)])
        self.parent.get_events.return_value = []
        self.child = MagicMock(assignees=[], id=_CHILD_ID)
        self.client.repo.get_issue.return_value = self.parent
        self.client.repo.create_issue.return_value = self.child

    def test_child_linked_as_sub_issue_when_enabled(self) -> None:
        with patch.object(config, _CHILD_SWITCH, True):
            created = self._create()

        self.assertIs(created, self.child)
        self.client.repo.get_issue.assert_called_once_with(_PARENT_NUMBER)
        self.parent.add_sub_issue.assert_called_once_with(_CHILD_ID)
        self.child.add_to_assignees.assert_called_once_with(_OWNER)

    def test_unassigned_parent_hands_child_labeler(self) -> None:
        self.parent.assignees = []
        self.parent.get_events.return_value = [
            FakeIssueEvent(event="labeled", actor=FakeUser(_OWNER), label=FakeLabel(_OPT_IN)),
        ]
        with patch.object(config, _CHILD_SWITCH, True), \
             patch.object(config, "PICKUP_LABEL", _OPT_IN):
            self._create()

        self.child.add_to_assignees.assert_called_once_with(_OWNER)

    def test_already_linked_is_not_an_error(self) -> None:
        self.parent.add_sub_issue.side_effect = GithubException(_ALREADY_LINKED, {"message": "already a sub-issue"})
        with patch.object(config, _CHILD_SWITCH, True):
            created = self._create()

        self.assertIs(created, self.child)
        self.child.add_to_assignees.assert_called_once_with(_OWNER)

    def test_link_failure_does_not_fail_creation(self) -> None:
        self.parent.add_sub_issue.side_effect = GithubException(_SERVER_ERROR, {"message": "boom"})
        with patch.object(config, _CHILD_SWITCH, True):
            created = self._create()

        self.assertIs(created, self.child)

    def test_disabled_does_not_link(self) -> None:
        with patch.object(config, _CHILD_SWITCH, False):
            self._create()

        self.client.repo.get_issue.assert_not_called()
        self.child.add_to_assignees.assert_not_called()

    def _create(self):
        return self.client.create_child_issue(
            title="A", body="do A", parent_number=_PARENT_NUMBER, labels=["workflow:ready"],
        )
