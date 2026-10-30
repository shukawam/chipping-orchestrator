# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a pending capture's road still has to stand on, and whether its run's accounting read back.

The label a capture reported under and the records its road froze say which
road it was; they cannot say whether that road is still there to finish. Each
stands on records another owner keeps, and a capture is handed on only while
they stand (`road_refusal`):

- a report under a stage only a pull request reaches -- `validating`,
  `in_review`, `fixing`, `resolving_conflict` -- is owed to the pull request
  the record names, so a record naming none has nothing to hand it to;
- a rewritten-head refresh answers the report debt that rewrite left
  (`report_rewrite_debt`), standing and naming the head the run started on or
  reported on: a debt paid, gone, or carried onto another head is a refresh
  nobody owes now;
- a late revision answers a live adjudication
  (`stages/decomposition/late_relabel._adjudicating`, asked when called, as the
  engine reaches every stage owner), and one that ended leaves the revision
  nothing to be measured by -- but a late record claiming a reading the
  comment cannot produce (`stages/implementing/late_claims._claims_a_reading`)
  answers that question for nobody, since its damage reads as no live
  adjudication too.

An auto-rebase anchor beside the capture is asked here as well
(`anchor_refusal`): one that reads as a commit is a rewrite of the branch no
recovery has finished, and one that does not is evidence nobody can read.

A record saying a prerequisite is gone proves the capture stale; one claiming
it in a shape nobody can read holds the capture.

A run whose usage checkpoint was refused or never confirmed is captured
`unresolved`, and an accounting checkpoint that neither landed nor read back
permits that run's accounting alone. So such a capture is handed on only
once the record reads its invocation's receipt back beside counters its
writers would write (`accounting_refusal`), and is held otherwise; nothing here
accounts it again, since the capture keeps no usage to account.

Only the record the dispatcher admitted is read, and nothing is written.
"""
from __future__ import annotations

import importlib

from orchestrator.git.base_sync import state as _base_sync_state
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.engine import (
    completion_records as _records,
    completion_recovery_models as _models,
    completion_routes as _routes,
    report_rewrite_debt as _rewrite_debt,
    stage_targets as _stage_targets,
    usage_counters as _usage_counters,
    usage_receipts as _usage_receipts,
)
from orchestrator.workflow.late_split import formats as _formats, payloads as _payloads
from orchestrator.workflow.state import WorkflowLabel

_PR_NUMBER = "pr_number"

# The anchor an auto rebase pins before git runs, spelled by the base sync.
_ANCHOR = _base_sync_state._PENDING_PUSH_SHA

# The stages only a pull request reaches, so a report under one is owed to the pull request the record names.
_PULL_REQUEST_STAGES = frozenset((
    WorkflowLabel.VALIDATING, WorkflowLabel.IN_REVIEW, WorkflowLabel.FIXING, WorkflowLabel.RESOLVING_CONFLICT,
))

_GONE = _models.Decision(_models.Standing.INVALID, _models.Reason.PREREQUISITE_GONE)


def road_refusal(state: PinnedState, capture: _records.CompletionCapture) -> _models.Decision | None:
    """Why the records the road `capture` was taken on stands on refuse it, over `state`; or None."""
    return _pull_request_refusal(state, capture) or _debt_refusal(state, capture) or _adjudication_refusal(
        state, capture,
    )


def accounting_refusal(state: PinnedState, capture: _records.CompletionCapture) -> _models.Decision | None:
    """Why `capture`'s run's accounting has not read back over `state`, where it was captured unresolved; or None."""
    if capture.accounting is not _records.CaptureAccounting.UNRESOLVED:
        return None
    receipts = _usage_receipts.read(state)
    counted = receipts is not None and not _usage_counters.miscounted(state.state_data)
    if counted and receipts.covers(capture.invocation):
        return None
    return _models.Decision(_models.Standing.UNCERTAIN, _models.Reason.ACCOUNTING_UNRESOLVED)


def _pull_request_refusal(state: PinnedState, capture: _records.CompletionCapture) -> _models.Decision | None:
    """A report under a pull-request stage on a record naming no pull request: gone."""
    if capture.handoff.origin in _PULL_REQUEST_STAGES and state.get(_PR_NUMBER) is None:
        return _GONE
    return None


def _debt_refusal(state: PinnedState, capture: _records.CompletionCapture) -> _models.Decision | None:
    """A rewritten-head refresh beside no debt, or one of another head, is gone; beside one nobody can read, held."""
    if capture.handoff.route is not _routes.CompletionRoute.REPORT_REFRESH:
        return None
    if not _rewrite_debt.carries_rewrite_debt(state):
        return _GONE
    debt = _rewrite_debt.read_rewrite_debt(state)
    if debt is None:
        return _models.Decision(_models.Standing.UNCERTAIN, _models.Reason.PREREQUISITE_UNREAD)
    return None if debt.rewritten_head in {capture.run.before_sha, capture.run.source_sha} else _GONE


def anchor_refusal(state: PinnedState) -> _models.Decision | None:
    """Why an auto rebase begun over the capture's branch, and not yet recovered, refuses it; or None.

    The anchor's recovery resets the checkout onto the anchor or pushes the
    replay whenever it cannot prove the attempt, so the commit the report is
    about is no longer the branch's to hand on: no road publishes over a
    rewrite no recovery has finished. Decided ahead of that recovery, so the
    capture is retired before the checkout is touched, and never left for the
    anchor and the capture to wait on each other. Only an anchor that reads
    as a commit proves that rewrite: one that does not is evidence nobody can
    read, and holds the capture.
    """
    anchor = state.get(_ANCHOR)
    if not anchor:
        return None
    if _payloads.as_hex(anchor, _formats.COMMIT_LENGTHS) is None:
        return _models.Decision(_models.Standing.UNCERTAIN, _models.Reason.ANCHOR_UNREAD)
    return _models.Decision(_models.Standing.INVALID, _models.Reason.ANCHORED)


def _adjudication_refusal(state: PinnedState, capture: _records.CompletionCapture) -> _models.Decision | None:
    """A late revision beside a late record nobody can read: held; beside no live adjudication: gone."""
    if capture.handoff.route is not _routes.CompletionRoute.LATE_REVISION:
        return None
    if importlib.import_module(_stage_targets._LATE_CLAIMS_OWNER)._claims_a_reading(state):
        return _models.Decision(_models.Standing.UNCERTAIN, _models.Reason.PREREQUISITE_UNREAD)
    late_relabel = importlib.import_module(_stage_targets._LATE_RELABEL_OWNER)
    return None if late_relabel._adjudicating(state) else _GONE
