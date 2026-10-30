# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What the dispatch does with a pending captured completion, ahead of the stage that would lose or repeat it.

Each case lands a capture through its own checkpoint, makes somebody else's
move, then dispatches the issue whole, with the stage handler stood in for,
and reads back what the dispatch reached and what the pinned comment carries.
An applicable capture is handed to its road's owner, admitted, and to nothing
else -- held where no road has an owner, as in this build; a stale one is
retired, keeping which invocation it was, and the stage runs as it would
without it; and an uncertain or damaged one holds the stage with nothing
written.
"""
from __future__ import annotations

import unittest
from types import MappingProxyType

from orchestrator.git.worktrees.models import ProbeAnswer
from orchestrator.workflow.engine import (
    completion_records as _records,
    completion_recovery_models as _models,
    completion_routes as _routes,
)
from orchestrator.workflow.state import WorkflowLabel
from tests.workflow.engine import completion_dispatch_support as _dispatch, completion_recovery_support as _support
from tests.workflow.engine.completion_turn_support import Case, Turn

_NUMBER = _support.NUMBER
_Reason = _models.Reason
_Standing = _models.Standing
_RETIRED = (_records.CaptureStage.RETIRED, _records.RetirementReason.INVALIDATED)
_RETIRED_STAGE = _records.CaptureStage.RETIRED.value
_FIELD = _support.FIELD
_HANDLED = (_NUMBER,)

_DONE = (str(WorkflowLabel.DONE),)

_VALIDATING = Turn(labels=(str(WorkflowLabel.VALIDATING),))

_ON_VALIDATING = WorkflowLabel.VALIDATING

# A drift resume read on `validating`, a rewritten-head refresh, and a late revision.
_DRIFT = _support.road(_routes.CompletionRoute.REQUIREMENTS_DRIFT, _ON_VALIDATING)
_REFRESH = _support.road(_routes.CompletionRoute.REPORT_REFRESH, _ON_VALIDATING)
_REVISION = _support.road(_routes.CompletionRoute.LATE_REVISION, WorkflowLabel.DECOMPOSING)

_DEBT = "developer_report_rewrite_debt"

_RECEIPTS = "issue_usage_receipts"

_EARLIER = "0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f"


def _debt_of(rewritten: str) -> MappingProxyType:
    """The pinned edit recording the report debt a rewrite of the pull request onto `rewritten` left."""
    owed = {"pr": _support.PR_NUMBER, "branch": _support.BRANCH, "previous_head": _EARLIER, "rewritten_head": rewritten}
    return MappingProxyType({_DEBT: owed})


# The capture's run read back as accounted after all, its receipt on the ledger.
_RECEIPT = (_support.ORDINAL, _support.NONCE)
_RECEIPTED = MappingProxyType({_RECEIPTS: {"floor": 0, "recent": [list(_RECEIPT)]}})

# A capture whose run's usage checkpoint never confirmed.
_UNACCOUNTED = MappingProxyType({"accounting": "unresolved"})

# Each road whose records still stand, and the move that leaves them so: a
# drift on a pull-request stage beside its pull request, a refresh beside the
# debt of the head its run started on, and an unaccounted run read back since.
_STANDING = MappingProxyType({
    "drift beside its pull request": Case(Turn(), None, pull_request=True, label=_ON_VALIDATING, road=_DRIFT),
    "refresh beside its debt": Case(
        Turn(edits=_debt_of(_support.BEFORE)), None, pull_request=True, label=_ON_VALIDATING, road=_REFRESH,
    ),
    "accounting read back": Case(Turn(members=_UNACCOUNTED, edits=_RECEIPTED), None),
})

# Another current-layout branch than the one the issue's record pins.
_OTHER_BRANCH = "orchestrator/chippingway__chipping-orchestrator/issue-1"

# Each proof that a capture no longer answers what the issue is.
_STALE = MappingProxyType({
    "closed": Case(Turn(closed=True), _Reason.ENDED),
    "done": Case(Turn(labels=_DONE), _Reason.ENDED, handled=False),
    "relabelled": Case(_VALIDATING, _Reason.RELABELLED),
    "requirements moved": Case(Turn(comment="Also cover the edge case."), _Reason.REQUIREMENTS_MOVED),
    "branch moved": Case(Turn(), _Reason.BRANCH_MOVED, run=(("branch", _OTHER_BRANCH),)),
    "checkout moved": Case(Turn(head=_support.ELSEWHERE), _Reason.CHECKOUT_MOVED),
    "pull request closed": Case(
        Turn(pull_request=MappingProxyType({"state": "closed"})), _Reason.PULL_REQUEST_ENDED, pull_request=True,
    ),
    "pull request pushed over": Case(
        Turn(pull_request=MappingProxyType({"sha": _support.ELSEWHERE})), _Reason.PULL_REQUEST_MOVED,
        pull_request=True,
    ),
    "pull request gone": Case(
        Turn(edits=MappingProxyType({"pr_number": _support.DROPPED})), _Reason.PREREQUISITE_GONE,
        pull_request=True, label=_ON_VALIDATING, road=_DRIFT,
    ),
    "refresh owed nothing": Case(
        Turn(), _Reason.PREREQUISITE_GONE, pull_request=True, label=_ON_VALIDATING, road=_REFRESH,
    ),
    "refresh of another head": Case(
        Turn(edits=_debt_of(_support.ELSEWHERE)), _Reason.PREREQUISITE_GONE,
        pull_request=True, label=_ON_VALIDATING, road=_REFRESH,
    ),
    "revision with no adjudication": Case(
        Turn(), _Reason.PREREQUISITE_GONE, label=WorkflowLabel.DECOMPOSING, road=_REVISION,
    ),
})

# Each reading nobody could take, or that nothing proves.
_UNREAD = MappingProxyType({
    "comment": Case(Turn(unanswered="read_pinned_state"), _Reason.RECORD_UNREAD),
    "issue": Case(Turn(unanswered="get_issue"), _Reason.ISSUE_UNREAD),
    "controls applied meanwhile": Case(
        Turn(refetched=(str(WorkflowLabel.IMPLEMENTING), "paused")), _Reason.ISSUE_UNREAD,
    ),
    "thread": Case(Turn(unanswered="comments_after"), _Reason.REQUIREMENTS_UNREAD),
    "branch refused": Case(Turn(edits=MappingProxyType({"branch": "orchestrator/issue-2427"})), _Reason.BRANCH_REFUSED),
    "pull request": Case(Turn(unanswered="get_pr"), _Reason.PULL_REQUEST_UNREAD, pull_request=True),
    "pull request head": Case(
        Turn(pull_request=MappingProxyType({"sha": None})), _Reason.PULL_REQUEST_UNREAD, pull_request=True,
    ),
    "checkout unreadable": Case(Turn(identity=ProbeAnswer.UNREADABLE), _Reason.CHECKOUT_UNPROVEN),
    "checkout not its own": Case(Turn(identity=ProbeAnswer.REFUTED), _Reason.CHECKOUT_UNPROVEN),
    "head unread": Case(Turn(head=""), _Reason.CHECKOUT_UNPROVEN),
    "checkout elsewhere": Case(Turn(), _Reason.CHECKOUT_UNPROVEN, run=(("worktree", "/elsewhere/issue-2427"),)),
    "refresh debt unreadable": Case(
        Turn(edits=MappingProxyType({_DEBT: "owed"})), _Reason.PREREQUISITE_UNREAD,
        pull_request=True, label=_ON_VALIDATING, road=_REFRESH,
    ),
    "accounting unresolved": Case(Turn(members=_UNACCOUNTED), _Reason.ACCOUNTING_UNRESOLVED),
    "accounting beside a damaged counter": Case(
        Turn(members=_UNACCOUNTED, edits=MappingProxyType({**_RECEIPTED, "issue_total_tokens": "many"})),
        _Reason.ACCOUNTING_UNRESOLVED,
    ),
})

# Each claim nothing may act on or clear: a capture that will not read, one
# of another comment, and a cycle the record has left or that will not read.
_DAMAGED = MappingProxyType({
    "null": Case(Turn(edits=MappingProxyType({_support.FIELD: None})), _Reason.DAMAGED),
    "a string": Case(Turn(edits=MappingProxyType({_support.FIELD: "pending"})), _Reason.DAMAGED),
    "a member missing": Case(Turn(members=MappingProxyType({"source": _support.DROPPED})), _Reason.DAMAGED),
    "another comment": Case(Turn(members=MappingProxyType({"comment": 999_999})), _Reason.NOT_THIS_RECORD),
    "another cycle": Case(Turn(edits=MappingProxyType({"late_cycle_id": 5})), _Reason.NOT_THIS_RECORD),
    "an unreadable cycle": Case(Turn(edits=MappingProxyType({"late_cycle_id": "five"})), _Reason.DAMAGED),
})


def _beside(record: dict) -> dict:
    """Every field a record carries beside its capture."""
    return {key: kept for key, kept in record.items() if key != _FIELD}


def _stage(record: dict) -> str:
    """The stage the capture a record carries stands at."""
    return record[_support.FIELD]["stage"]


class ApplicableCaptureTest(unittest.TestCase):
    """A capture every reading still admits goes to its road's owner, and nowhere else."""

    def test_its_road_owner_is_handed_it(self) -> None:
        # Handed the capture, the issue read afresh, the label, and the head
        # the pull request stood on, the owner answers for the tick: stopping
        # it holds the handler, carrying on reaches it. Admission itself
        # writes nothing, charges no run, and clears no park.
        for stops, pull_request in ((True, False), (False, True)):
            with self.subTest(stops=stops, pull_request=pull_request):
                world = _support.CapturedWorld(pull_request=pull_request)
                captured = world.captured()

                seen = _dispatch.observed(world, _dispatch.RoadOwner(stops=stops))

                self._admitted(seen.handed, captured, _support.BEFORE if pull_request else None)
                self.assertEqual(seen.ran, () if stops else _HANDLED)
                self.assertTrue(seen.untouched)

    def test_its_road_standing_hands_it_on(self) -> None:
        # Each road's own records still standing -- its pull request, the debt
        # a refresh answers, and the receipt of an unaccounted run -- admit it.
        for name, case in _STANDING.items():
            with self.subTest(name):
                world = _support.CapturedWorld(case.label, pull_request=case.pull_request)
                captured = world.captured(case.road)

                seen = _dispatch.observed(world, _dispatch.RoadOwner(), case.turn)

                self.assertEqual([admitted.capture.invocation for admitted in seen.handed], [captured.invocation])

    def test_a_road_no_owner_takes_holds_it(self) -> None:
        # As in this build: nothing finishes the capture, so nothing may run
        # the work again over it -- every tick holds, and none writes.
        world = _support.CapturedWorld()
        world.captured()
        for tick in ("first", "second"):
            with self.subTest(tick=tick):
                seen = _dispatch.observed(world)
                self.assertEqual(seen.ran, ())
                self.assertTrue(seen.untouched)
                self.assertEqual(_stage(seen.after), _records.CaptureStage.PENDING)

    def _admitted(self, handed: tuple, captured: _records.CompletionCapture, head: str | None) -> None:
        """`handed` is the one admitted handoff of `captured`, on the issue read afresh, at `head`."""
        self.assertEqual(len(handed), 1)
        admitted = handed[0]
        self.assertEqual(admitted.capture, captured)
        self.assertEqual((admitted.issue.number, admitted.label), (_NUMBER, WorkflowLabel.IMPLEMENTING))
        self.assertEqual(admitted.pull_request_head, head)


class StaleCaptureTest(unittest.TestCase):
    """A capture a reading proved stale is retired, and the stage runs as it would without one."""

    def test_each_proof_of_staleness_retires_it(self) -> None:
        for name, case in _STALE.items():
            with self.subTest(name):
                world = _support.CapturedWorld(case.label, pull_request=case.pull_request)
                captured = world.captured(case.road, **dict(case.run))

                seen = _dispatch.observed(world, _dispatch.RoadOwner(), case.turn)

                self.assertTrue(seen.says(case.reason), seen.said)
                self._retired(seen, captured, handled=case.handled)

    def test_an_unlanded_retirement_holds_it(self) -> None:
        # Refused, the capture stands and the next dispatch decides afresh;
        # never confirmed, the next dispatch reads what landed and runs the
        # stage behind it, retiring nothing twice.
        for failure, retired_by_then in (("refused", False), ("lost", True)):
            with self.subTest(failure=failure):
                self._retried(failure, retired_by_then=retired_by_then)

    def _retried(self, failure: str, *, retired_by_then: bool) -> None:
        """A retirement `failure` keeps from landing holds the dispatch, and the one after it settles the capture."""
        world = _support.CapturedWorld()
        world.captured()
        failing = getattr(world.github.pinned_failures, failure)
        failing.add(_NUMBER)

        held = _dispatch.observed(world, turn=_VALIDATING)

        failing.discard(_NUMBER)
        self.assertEqual(held.ran, ())
        self.assertEqual(_stage(held.after) == _RETIRED_STAGE, retired_by_then)
        again = _dispatch.observed(world)
        self.assertEqual((again.ran, _stage(again.after)), (_HANDLED, _RETIRED_STAGE))
        self.assertEqual(again.writes, 0 if retired_by_then else 1)

    def _retired(self, seen: _dispatch.Observed, captured: _records.CompletionCapture, *, handled: bool) -> None:
        """`captured` was retired as invalidated, nothing else moved, and the stage ran behind it where `handled`."""
        retired = _support.read_capture(seen.after)
        self.assertEqual((retired.stage, retired.reason), _RETIRED)
        self.assertEqual(retired.invocation, captured.invocation)
        self.assertEqual(_beside(seen.after), _beside(seen.before), "the invalidation owns the capture alone")
        ran = _HANDLED if handled else ()
        self.assertEqual((seen.ran, seen.handed), (ran, ()))


class UndecidedCaptureTest(unittest.TestCase):
    """A capture nothing can decide on holds the stage, and nothing is written over it."""

    def test_an_unread_world_holds_it(self) -> None:
        for name, case in _UNREAD.items():
            with self.subTest(name):
                self._held(case, _Standing.UNCERTAIN)

    def test_a_damaged_capture_is_held(self) -> None:
        for name, case in _DAMAGED.items():
            with self.subTest(name):
                self._held(case, _Standing.DAMAGED)

    def _held(self, case: Case, standing: _Standing) -> None:
        """`case`'s move holds the dispatch under `standing`, with nothing handed on, run, or written."""
        world = _support.CapturedWorld(case.label, pull_request=case.pull_request)
        world.captured(case.road, **dict(case.run))

        seen = _dispatch.observed(world, _dispatch.RoadOwner(), case.turn)

        self.assertTrue(seen.says(case.reason, standing), seen.said)
        self.assertEqual((seen.ran, seen.handed), ((), ()))
        self.assertTrue(seen.untouched)


if __name__ == "__main__":
    unittest.main()
