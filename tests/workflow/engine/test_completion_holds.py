# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The holds a pending captured completion waits through, and the frozen handoff it is decided on.

An operator's `paused` or `backlog`, a dependency hold, the `ready`
decision that answers one, an issue a human unlabeled, and a spent run
ledger each keep the capture as it stands: nothing is handed on, retired,
released, re-baselined, or charged, and each stage that runs there runs as
it would with no capture -- a dependency hold beside an auto-rebase anchor
included, which the anchor's own hold answers while the base refresh keeps
the branch for the capture. A handoff frozen over a pinned record is handed
on only while that record still reads as the launch read it.
"""
from __future__ import annotations

import unittest
from types import MappingProxyType
from unittest.mock import patch

from orchestrator.git.base_sync import refresh_selection as _refresh_selection
from orchestrator.github.labels import PAUSED_LABEL
from orchestrator.workflow.engine import (
    completion_checkpoint as _checkpoint,
    completion_frozen as _frozen,
    completion_records as _records,
    completion_recovery as _recovery,
    completion_recovery_models as _models,
    completion_routes as _routes,
)
from orchestrator.workflow.state import WorkflowLabel
from tests.workflow.engine import completion_dispatch_support as _dispatch, completion_recovery_support as _support
from tests.workflow.engine.completion_turn_support import Turn
from tests.workflow.fixtures import _TEST_SPEC

_NUMBER = _support.NUMBER
_IMPLEMENTING = str(WorkflowLabel.IMPLEMENTING)

# What a spent run ledger's park stands on, and the charges beside it.
_RUN_LIMIT_PARK = MappingProxyType({"awaiting_human": True, "park_reason": "agent_run_limit"})

_CHARGES = ("agent_runs_used", "issue_agent_runs")

# A record a road's handoff is frozen over, as the launch read it and as another road moves it.
_FROZEN_RECORD = "review_round"

_ROUND_AT_LAUNCH = 3

_ROUND_MOVED = 4

# The pinned readings a dispatch takes up to its retirement's own: the
# dispatcher's, the capture's read-back, and the retirement's.
_RETIREMENT_READING = 3

# The holds a capture waits through, by the labels the issue wears, and whether a stage handler runs there.
_WAITS = (
    ((str(WorkflowLabel.BLOCKED),), True),
    ((str(WorkflowLabel.READY),), True),
    ((), False),
)

_PAUSED = Turn(labels=(_IMPLEMENTING, PAUSED_LABEL))

_PARKED = Turn(edits=_RUN_LIMIT_PARK)

_RECORD_MOVED = Turn(edits=MappingProxyType({_FROZEN_RECORD: _ROUND_MOVED}))

_BLOCKED = Turn(labels=(str(WorkflowLabel.BLOCKED),))

# An auto-rebase anchor a hand edit left beside the capture, the park its own
# hold answers one carrying no terms with, and a human's reconciliation of both.
_ANCHOR = "pending_auto_base_rebase_push_sha"
_ANCHORED = MappingProxyType({_ANCHOR: _support.BEFORE})
_STRANDED = "auto_base_rebase_failed"
_RECONCILED = MappingProxyType(dict.fromkeys((_ANCHOR, "awaiting_human", "park_reason"), _support.DROPPED))

# A live late adjudication of the issue's own candidate, measured past its ceiling.
_ADJUDICATING = MappingProxyType({
    "late_cycle_id": 1,
    "late_generation": 1,
    "late_root_issue": _NUMBER,
    "late_current_issue": _NUMBER,
    "late_lineage_depth": 0,
    "late_candidate_sha": _support.SOURCE,
    "late_base_sha": _support.BEFORE,
    "late_threshold": 100,
    "late_additions": 500,
    "late_phase": "adjudicating",
})

# A hand edit leaving that adjudication's ceiling as nothing its reader takes.
_UNREADABLE_MEASUREMENT = Turn(edits=MappingProxyType({"late_threshold": "unreadable"}))


def _revised_world() -> tuple[_support.CapturedWorld, _records.CompletionCapture]:
    """A world under a live late adjudication, its developer revision captured in that adjudication's cycle."""
    world = _support.CapturedWorld(WorkflowLabel.DECOMPOSING)
    world.hand_edit(**_ADJUDICATING)
    return world, world.captured(_support.road(_routes.CompletionRoute.LATE_REVISION, WorkflowLabel.DECOMPOSING))


def _frozen_world() -> tuple[_support.CapturedWorld, _records.CompletionCapture]:
    """A world whose capture's handoff froze the review round as the launch read it."""
    world = _support.CapturedWorld()
    world.hand_edit(**{_FROZEN_RECORD: _ROUND_AT_LAUNCH})
    frozen = _frozen.frozen_over(world.github.read_pinned_state(world.issue), (_FROZEN_RECORD,))
    return world, world.captured(_support.road(frozen=frozen))


class WaitingCaptureTest(unittest.TestCase):
    """A hold the capture waits through leaves it captured, and the stage runs as it would."""

    def test_a_dependency_hold_keeps_it(self) -> None:
        # The dependency walk and the ready decision run; an issue a human
        # unlabeled is left where they left it. None of them is handed the
        # capture, and nothing is written over it -- no release, no baseline.
        for labels, handled in _WAITS:
            with self.subTest(labels=labels):
                world = _support.CapturedWorld()
                world.captured()

                seen = _dispatch.observed(world, _dispatch.RoadOwner(), Turn(labels=labels))

                ran = (_NUMBER,) if handled else ()
                self.assertEqual((seen.ran, seen.handed), (ran, ()))
                self.assertTrue(seen.untouched)

    def test_an_anchor_beside_a_wait_keeps_it(self) -> None:
        # The capture waits through the dependency hold rather than being
        # retired for the anchor: the anchor's own hold answers it, on a
        # label the base refresh does not drive, with a park that leaves the
        # checkout where it stands, and holds the walk for that tick. Once a
        # human reconciles it, the walk runs; the capture is pending all
        # along, and the refresh keeps its branch on either side.
        world = _support.CapturedWorld()
        captured = world.captured()
        world.hand_edit(**_ANCHORED)

        held = _dispatch.observed(world, _dispatch.RoadOwner(), _BLOCKED)
        self.assertEqual((held.ran, held.handed), ((), ()))
        self.assertEqual(held.after["park_reason"], _STRANDED)
        self.assertTrue(self._branch_kept(world))
        world.hand_edit(**_RECONCILED)
        walked = _dispatch.observed(world, _dispatch.RoadOwner())

        self.assertEqual((walked.ran, walked.handed), ((_NUMBER,), ()))
        self.assertTrue(self._branch_kept(world))
        for seen in (held, walked):
            self.assertEqual(_support.read_capture(seen.after), captured)

    def test_an_operator_control_keeps_all_off(self) -> None:
        # Applied before the dispatch, nothing is read and nothing reached;
        # and on the one road a held issue is let through -- a close somebody
        # observed -- the recovery stands down without a reading.
        world = _support.CapturedWorld()
        world.captured()

        seen = _dispatch.observed(world, _dispatch.RoadOwner(), _PAUSED)

        self.assertEqual((seen.ran, seen.handed), ((), ()))
        self.assertTrue(seen.untouched)
        state = world.github.read_pinned_state(world.issue)
        with world.checkout(), patch.object(world.github, "get_issue", side_effect=AssertionError("read")):
            self.assertFalse(_recovery.capture_holds_the_tick(
                world.github, _TEST_SPEC, world.issue, WorkflowLabel.IMPLEMENTING, state,
            ))

    def test_a_run_limit_park_holds_first(self) -> None:
        # Recovering paid work buys no run: the spent ledger's hold is asked
        # first, and the park, the charges, and the capture all stand.
        world = _support.CapturedWorld()
        world.captured()

        seen = _dispatch.observed(world, _dispatch.RoadOwner(), _PARKED)

        self.assertEqual((seen.ran, seen.handed), ((), ()))
        self.assertEqual(seen.after[_support.FIELD], seen.before[_support.FIELD])
        parked = {key: seen.after[key] for key in _RUN_LIMIT_PARK}
        self.assertEqual(parked, dict(_RUN_LIMIT_PARK))
        charged = {seen.after[key] for key in _CHARGES}
        self.assertEqual(charged, {_support.RUNS_USED})

    def test_a_resolved_capture_leaves_the_stage(self) -> None:
        world = _support.CapturedWorld()
        captured = world.captured()
        state = world.github.read_pinned_state(world.issue)
        _checkpoint.retire(world.github, world.issue, state, captured.invocation, _records.RetirementReason.INVALIDATED)

        seen = _dispatch.observed(world, _dispatch.RoadOwner())

        self.assertEqual((seen.ran, seen.handed), ((_NUMBER,), ()))
        self.assertTrue(seen.untouched)

    def _branch_kept(self, world: _support.CapturedWorld) -> bool:
        """Whether the base refresh holds the world's branch still over its pinned comment as it reads now."""
        state = world.github.read_pinned_state(world.issue)
        return _refresh_selection._state_holds_the_branch(_NUMBER, state)


class FrozenHandoffTest(unittest.TestCase):
    """A handoff frozen over a record another road has since moved is no longer the one the run answered."""

    def test_a_moved_frozen_record_retires_it(self) -> None:
        world, captured = _frozen_world()

        seen = _dispatch.observed(world, _dispatch.RoadOwner(), _RECORD_MOVED)

        retired = _support.read_capture(seen.after)
        self.assertEqual(retired.stage, _records.CaptureStage.RETIRED)
        self.assertEqual(retired.invocation, captured.invocation)
        self.assertEqual((seen.ran, seen.handed), ((_NUMBER,), ()))
        self.assertEqual(seen.after[_FROZEN_RECORD], _ROUND_MOVED, "the moved record is the other road's")

    def test_a_repair_behind_the_proof_keeps_it(self) -> None:
        # The record that proved the capture stale is put back by hand after
        # the dispatch read it and before the retirement's own reading: the
        # retirement is decided on the reading the proof was taken over, so it
        # is refused, nothing is written or run, and the next dispatch -- on
        # the repaired record -- hands the capture on.
        world, captured = _frozen_world()
        world.hand_edit(**{_FROZEN_RECORD: _ROUND_MOVED})
        repaired = _support.RepairedBehind(world, _RETIREMENT_READING, **{_FROZEN_RECORD: _ROUND_AT_LAUNCH})

        with patch.object(world.github, "read_pinned_state", side_effect=repaired):
            held = _dispatch.observed(world, _dispatch.RoadOwner())

        self.assertEqual(_support.read_capture(held.after), captured)
        self.assertEqual(held.writes, 0, "nothing is written over the capture")
        self.assertEqual((held.ran, held.handed), ((), ()))
        self.assertIn("EVIDENCE_MOVED", held.said)
        handed = _dispatch.observed(world, _dispatch.RoadOwner()).handed
        self.assertEqual([admitted.capture for admitted in handed], [captured])

    def test_an_unmoved_frozen_record_hands_it_on(self) -> None:
        world, captured = _frozen_world()

        seen = _dispatch.observed(world, _dispatch.RoadOwner())

        self.assertEqual([admitted.capture for admitted in seen.handed], [captured])


class LateRevisionTest(unittest.TestCase):
    """A late revision is handed on over the live adjudication it answers, and held over one nobody can read."""

    def test_a_live_adjudication_hands_it_on(self) -> None:
        world, captured = _revised_world()

        seen = _dispatch.observed(world, _dispatch.RoadOwner())

        self.assertEqual([admitted.capture for admitted in seen.handed], [captured])

    def test_an_unreadable_measurement_holds_it(self) -> None:
        # A measurement that will not read is no live adjudication to the
        # reader that asks, and no proof one ended either: the capture is
        # kept, with nothing written, handed on, or run.
        world, captured = _revised_world()

        seen = _dispatch.observed(world, _dispatch.RoadOwner(), _UNREADABLE_MEASUREMENT)

        held = seen.says(_models.Reason.PREREQUISITE_UNREAD, _models.Standing.UNCERTAIN)
        self.assertTrue(held, seen.said)
        self.assertEqual(_support.read_capture(seen.after), captured)
        self.assertEqual((seen.ran, seen.handed), ((), ()))
        self.assertTrue(seen.untouched)


if __name__ == "__main__":
    unittest.main()
