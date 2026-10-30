# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""A captured developer completion holds its checkout until a transaction owns its report or an invalidation ends it.

The refresh runs ahead of the dispatcher's recovery on every tick, the first
unpaused one above all, so a pending capture -- and one nobody can read, which
may be the one a recovery needs -- keeps the commit its report is about where
the run left it. The transfer that hands the report to the delivery hands the
freeze to the delivery's own records in the same commit, and their settlement
releases it; an invalidated capture holds nothing. Accounting alone never
holds a checkout. Beside an auto-rebase anchor the capture is set aside for
the anchor's own recovery, which finishes the rewrite already made and starts
none: the selection asked again unanchored holds the branch for it.
"""
from __future__ import annotations

import unittest
from types import MappingProxyType
from unittest.mock import MagicMock

from orchestrator.git.base_sync import refresh_selection as _selection
from orchestrator.git.worktrees import naming as _naming
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import base_refresh, completion_records as _records, completion_spelling as _spelling
from tests.git.base_sync.sync_test_support import _patch_base_sync
from tests.support.fakes import FakeGitHubClient, make_issue
from tests.workflow.engine import completion_test_support as _captures
from tests.workflow.fixtures import _TEST_SPEC, LABEL_FIXING, LABEL_IMPLEMENTING

_NUMBER = 2427
_WORKTREE = _TEST_SPEC.target_root / f"issue-{_NUMBER}"

_FIELD = _records.DEVELOPER_COMPLETION

_RECEIPT = "issue-2426-report-3"

_REVISION = 3

_DELIVERY_KEY = "developer_report_delivery"

_PENDING_KEY = "developer_report_pending"

# Neither report record outstanding: the report a handoff became has settled.
_SETTLED = MappingProxyType({_DELIVERY_KEY: None, _PENDING_KEY: None})

# The refresh's two routes: a pre-PR checkout, and one a pull request publishes on the issue's own branch.
_ROUTES = (
    (LABEL_IMPLEMENTING, MappingProxyType({})),
    (LABEL_FIXING, MappingProxyType({"pr_number": 42, "branch": _naming._branch_name(_TEST_SPEC, _NUMBER)})),
)

# Accounting a checkpoint landed for the issue's invocations, and the totals it counts.
_ACCOUNTED = MappingProxyType({
    "issue_usage_receipts": {"floor": 2, "recent": [[3, "0000000000000003"]]},
    "issue_agent_runs": 3,
    "issue_total_tokens": 1200,
})

_ANCHOR = "pending_auto_base_rebase_push_sha"


def _spelled(stage: _records.CaptureStage) -> dict:
    """A capture at `stage`, spelled whole as its checkpoint writes one."""
    world = _captures.seeded()
    invocation = world.invocation(ordinal=_REVISION)
    if stage is _records.CaptureStage.PENDING:
        return _spelling.spelled(world.completion(ordinal=_REVISION))
    if stage is _records.CaptureStage.HANDED_OFF:
        return _spelling.spelled(_records.ResolvedCapture(
            invocation=invocation, stage=stage, receipt=_RECEIPT, report_revision=_REVISION,
            branch=_captures.BRANCH, source_sha=_captures.SOURCE,
        ))
    return _spelling.spelled(_records.ResolvedCapture(
        invocation=invocation, stage=stage, reason=_records.RetirementReason.INVALIDATED,
    ))


def _without(spelled: dict, member: str) -> dict:
    """`spelled` with `member` taken off."""
    return {key: kept for key, kept in spelled.items() if key != member}


def _unresolved() -> MappingProxyType:
    """A pending capture, and every shape of one nobody can read: none of them is a release."""
    pending = _spelled(_records.CaptureStage.PENDING)
    handed_off = _spelled(_records.CaptureStage.HANDED_OFF)
    return MappingProxyType({
        "pending": pending,
        "null": None,
        "not an object": "pending",
        "no stage": _without(pending, "stage"),
        "a stage nobody writes": {**pending, "stage": "settled"},
        "a pending capture called handed off": {**pending, "stage": "handed_off"},
        "a handoff missing a member": _without(handed_off, "receipt"),
        "a handoff with a member too many": {**handed_off, "report": "the report"},
    })


def _synced(label: str, **seeded) -> bool:
    """Whether one refresh of the seeded issue's checkout went on to read its lag."""
    gh = FakeGitHubClient()
    gh.add_issue(make_issue(_NUMBER, label=label))
    gh.seed_state(_NUMBER, **seeded)
    lag = MagicMock(return_value=MagicMock(returncode=0, stdout="0"))
    rebase = MagicMock(return_value=(True, []))
    with _patch_base_sync(git=lag, dirty=MagicMock(return_value=[]), rebase=rebase):
        base_refresh._sync_worktree_with_base(gh, _TEST_SPEC, _WORKTREE, _NUMBER)
    return lag.called


class CompletionFreezeTest(unittest.TestCase):
    """Which captures hold the checkout, and what releases one."""

    def test_an_unresolved_capture_holds_it(self) -> None:
        # On the pre-PR route and on a pull request's alike.
        for name, captured in _unresolved().items():
            for label, route in _ROUTES:
                with self.subTest(name, label=label):
                    self.assertFalse(_synced(label, **{_FIELD: captured, **route}))

    def test_a_resolved_capture_holds_nothing(self) -> None:
        # Retired, or handed off with the report it became settled: the
        # checkout syncs as one that never captured anything, and so does one
        # carrying only the accounting its runs left.
        for stage in (_records.CaptureStage.HANDED_OFF, _records.CaptureStage.RETIRED):
            with self.subTest(stage=stage):
                resolved = {_FIELD: _spelled(stage), **_SETTLED}
                self.assertTrue(_synced(LABEL_IMPLEMENTING, **resolved))
        with self.subTest("accounting alone"):
            self.assertTrue(_synced(LABEL_IMPLEMENTING, **_ACCOUNTED))

    def test_its_report_takes_the_freeze_over(self) -> None:
        # The transfer writes the delivery beside the handed-off capture, and
        # the binding turns it into the transaction: each holds in turn, and
        # the settlement that spends the last releases the checkout.
        label, route = _ROUTES[1]
        handed_off = {_FIELD: _spelled(_records.CaptureStage.HANDED_OFF), **route}
        delivery = {"revision": _REVISION, "receipt": _RECEIPT}
        for owner in ({_DELIVERY_KEY: delivery}, {_DELIVERY_KEY: None, _PENDING_KEY: delivery}):
            with self.subTest(owner=sorted(owner)):
                self.assertFalse(_synced(label, **handed_off, **owner))
        self.assertTrue(_synced(label, **handed_off, **_SETTLED))

    def test_an_anchor_recovers_ahead_of_it(self) -> None:
        # Beside an anchor the capture is set aside, as a report in flight is:
        # the dispatcher holds the handlers behind the anchor, so a capture that
        # froze its recovery out too would leave neither to move. The selection
        # asked again once that recovery takes the anchor down holds the branch.
        captured = {_FIELD: _spelled(_records.CaptureStage.PENDING)}
        anchored = PinnedState(state_data={**captured, _ANCHOR: _captures.BEFORE})

        self.assertFalse(_selection._state_holds_the_branch(_NUMBER, anchored))
        self.assertTrue(_selection._state_holds_the_branch(_NUMBER, PinnedState(state_data=captured)))


if __name__ == "__main__":
    unittest.main()
