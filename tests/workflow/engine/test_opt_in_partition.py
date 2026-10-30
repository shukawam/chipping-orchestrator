# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""`PICKUP_LABEL` drops issues it would refuse before the poll's partition.

An unopted, workflow-label-less issue folded into the family bucket would make
the whole bucket cap-counted every tick, as a parked `backlog` issue would, and
starve fan-out work such as a `ready` issue under ``parallel_limit=1``.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.workflow.engine import dispatch_partition, poll_reading
from tests.support.fakes import FakeGitHubClient, FakeIssueEvent, FakeLabel, FakeUser, make_issue
from tests.workflow.fixtures import _TEST_SPEC

_OPT_IN = "agent-ready"
_OWNER = "shukawam"
_READY = "workflow:ready"


def _opted(issue_number: int):
    issue = make_issue(issue_number)
    issue.labels.append(FakeLabel(_OPT_IN))
    issue.events.append(
        FakeIssueEvent(event="labeled", actor=FakeUser(_OWNER), label=FakeLabel(_OPT_IN)),
    )
    return issue


class OptInPartitionTest(unittest.TestCase):
    def setUp(self) -> None:
        patches = (
            patch.object(config, "PICKUP_LABEL", _OPT_IN),
            patch.object(config, "ALLOWED_ISSUE_AUTHORS", (_OWNER,)),
        )
        for active in patches:
            active.start()
            self.addCleanup(active.stop)

    def test_unopted_issue_is_skipped_by_routing(self) -> None:
        gh = FakeGitHubClient()
        issue = make_issue(1)
        gh.add_issue(issue)
        self.assertEqual(poll_reading._read_issue_routing(gh, _TEST_SPEC, issue), (True, None))

    def test_opted_issue_is_routed(self) -> None:
        gh = FakeGitHubClient()
        issue = _opted(1)
        gh.add_issue(issue)
        self.assertEqual(poll_reading._read_issue_routing(gh, _TEST_SPEC, issue), (False, None))

    def test_unopted_issues_stay_out_of_family_bucket(self) -> None:
        gh = FakeGitHubClient()
        for number in (1, 2):
            gh.add_issue(make_issue(number))
        gh.add_issue(make_issue(3, label=_READY))

        partition = dispatch_partition._partition_pollable_issues(gh, _TEST_SPEC)

        self.assertEqual(partition.family_numbers, [])
        self.assertEqual(partition.fanout_numbers, [3])
