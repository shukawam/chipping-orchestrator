# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A child a crash left created and unrecorded is linked as a sub-issue when adopted.

The create links its own child; these are the two recoveries that adopt one
the create never got to record, so the link is not lost to the crash.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.workflow.stages.decomposition import split_receipts as _split_receipts
from orchestrator.workflow.state import WorkflowLabel
from tests.support.fakes import FakeGitHubClient, make_issue
from tests.workflow.fixtures import _TEST_SPEC
from tests.workflow.stages.decomposition import replacement_lineage_support as _support
from tests.workflow.stages.decomposition.late_test_support import LATE_ISSUE_NUMBER
from tests.workflow.stages.decomposition.test_late_orphans import OrphanAdoptionCase

_CHILD_SWITCH = "CHILD_AS_SUB_ISSUE"
_ATTEMPT = "0123456789abcdef"


class SplitOrphanLinkTest(unittest.TestCase):
    def test_adopted_orphan_is_linked_when_enabled(self) -> None:
        github = FakeGitHubClient([make_issue(_support.PARENT, body=_support.EDITED_BODY)])
        github.seed_state(_support.PARENT, **_support.record(None, split_attempt=_ATTEMPT).data)
        stamp = _split_receipts.receipt(_support.PARENT, _ATTEMPT, 0, None)
        orphan = github.create_child_issue(
            title="t",
            body=f"the declared slice\n\n{stamp}",
            parent_number=_support.PARENT,
            labels=[WorkflowLabel.BLOCKED],
        )
        parent = github.get_issue(_support.PARENT)

        with patch.object(config, _CHILD_SWITCH, True):
            _split_receipts.adopt_unrecorded(
                github, _TEST_SPEC, parent, github.read_pinned_state(parent), [],
            )

        self.assertEqual(github.linked_children, [(_support.PARENT, orphan.number)])


class LateOrphanLinkTest(OrphanAdoptionCase, unittest.TestCase):
    def test_late_orphan_is_linked_when_enabled(self) -> None:
        orphan = self._crashed().number

        with patch.object(config, _CHILD_SWITCH, True):
            self._resume()

        self.assertEqual(self.github.linked_children, [(LATE_ISSUE_NUMBER, orphan)])
