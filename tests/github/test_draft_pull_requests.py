# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""`OPEN_PR_AS_DRAFT` turns every pull request the client opens into a draft."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from orchestrator import config
from orchestrator.github.client import GitHubClient

_BRANCH = "orchestrator/issue-7"
_BASE = "main"


class DraftPullRequestTest(unittest.TestCase):
    def setUp(self) -> None:
        # Bypass the networked __init__; open_pr reads only `self.repo`.
        self.gh = GitHubClient.__new__(GitHubClient)
        self.gh.repo = MagicMock()

    def test_open_pr_as_draft_when_enabled(self) -> None:
        create_pull = self.gh.repo.create_pull
        with patch.object(config, "OPEN_PR_AS_DRAFT", True):
            self.gh.open_pr(branch=_BRANCH, base=_BASE, title="Issue 7", body="closes #7")

        self.assertIs(create_pull.call_args.kwargs["draft"], True)
