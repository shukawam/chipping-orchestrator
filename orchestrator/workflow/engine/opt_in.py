# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The `PICKUP_LABEL` opt-in gate in front of the roads a human label opens.

An unlabeled issue would be picked up, and a `question` or `discussion` label
starts a conversation, whoever applied it. With `PICKUP_LABEL` set, those
entries wait until the issue wears the opt-in label and the newest
application of it came from an `ALLOWED_ISSUE_AUTHORS` login. Every other
stage is the orchestrator's own continuation and is never gated, so removing
the label from an issue in flight does not strand it.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.config import models as _config_models
from orchestrator.github import labels as _labels
from orchestrator.workflow.state import WorkflowLabel

log = logging.getLogger("orchestrator.workflow")

_GATED_STAGES = frozenset((None, WorkflowLabel.QUESTION, WorkflowLabel.DISCUSSION))


def _opt_in_refuses(
    spec: _config_models.RepoSpec, issue: Issue, label: str | None,
) -> bool:
    """Whether the opt-in gate keeps this issue out of its stage this tick."""
    opt_in_label = config.PICKUP_LABEL
    if not opt_in_label or label not in _GATED_STAGES:
        return False
    if not _labels.issue_has_label(issue, opt_in_label):
        # Most open issues never carry the label and recur every poll, so
        # this refusal stays out of the INFO log.
        return _refused(
            spec, issue, "does not carry the opt-in label", level=logging.DEBUG,
        )
    try:
        applier = _labels.last_labeler(issue, opt_in_label)
    except Exception:
        log.exception(
            "repo=%s issue=#%s opt-in label history could not be read",
            spec.slug, issue.number,
        )
        return True
    allowed = {login.lower() for login in config.ALLOWED_ISSUE_AUTHORS}
    if (applier or "").lower() not in allowed:
        return _refused(spec, issue, f"opt-in label applied by {applier!r}")
    return False


def _refused(
    spec: _config_models.RepoSpec,
    issue: Issue,
    reason: str,
    *,
    level: int = logging.INFO,
) -> bool:
    log.log(
        level,
        "repo=%s issue=#%s %s; skipping (PICKUP_LABEL=%r)",
        spec.slug, issue.number, reason, config.PICKUP_LABEL,
    )
    return True
