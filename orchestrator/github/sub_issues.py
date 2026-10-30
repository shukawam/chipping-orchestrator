# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Link a split's child under its parent as a GitHub sub-issue, and give it an owner.

Driven by `CHILD_AS_SUB_ISSUE`. Both writes are bookkeeping on a child that
already exists, so each is logged and swallowed on failure: losing the child
to a missing link would cost the split far more than a link a human adds by
hand.
"""
from __future__ import annotations

import logging

from github.Issue import Issue

from orchestrator import config
from orchestrator.github import labels as _labels

log = logging.getLogger("orchestrator.github")

# What GitHub answers a sub-issue link it already holds.
_ALREADY_LINKED = 422


class GitHubSubIssueMixin:
    """The client's sub-issue link, on whatever repository it was built for."""

    repo: object

    def link_child_issue(self, parent_number: int, child: Issue) -> None:
        """Register `child` as a sub-issue of `parent_number`; a no-op while the switch is off."""
        if not config.CHILD_AS_SUB_ISSUE:
            return
        try:
            parent = self.repo.get_issue(parent_number)
        except Exception:
            log.exception("issue=#%s could not be read to link child #%s", parent_number, child.number)
            return
        _register_sub_issue(parent, child)
        _assign_child(parent, child)


def _register_sub_issue(parent: Issue, child: Issue) -> None:
    """Link `child` under `parent`; a link GitHub already holds is success."""
    try:
        parent.add_sub_issue(child.id)
    except Exception as error:
        if getattr(error, "status", None) == _ALREADY_LINKED:
            log.info("issue=#%s child #%s is already a sub-issue", parent.number, child.number)
            return
        log.exception("issue=#%s could not link child #%s as a sub-issue", parent.number, child.number)


def _assign_child(parent: Issue, child: Issue) -> None:
    """Give an unassigned child the parent's assignees, else the opt-in labeler."""
    if child.assignees:
        return
    try:
        owners = _owners(parent)
    except Exception:
        log.exception("issue=#%s owners could not be read for child #%s", parent.number, child.number)
        return
    if not owners:
        return
    try:
        child.add_to_assignees(*owners)
    except Exception:
        log.exception("issue=#%s could not assign child #%s", parent.number, child.number)


def _owners(parent: Issue) -> list[str]:
    """The parent's assignees, or whoever last applied `PICKUP_LABEL` to it."""
    owners = [assignee.login for assignee in parent.assignees]
    if owners or not config.PICKUP_LABEL:
        return owners
    applier = _labels.last_labeler(parent, config.PICKUP_LABEL)
    return [applier] if applier else []
