# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""`COMMUNITY_PR_SWEEP=off` leaves pull requests the orchestrator did not open alone."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import config
from orchestrator.workflow.engine import community
from tests.support.fakes import FakeGitHubClient
from tests.workflow.engine.community_test_support import (
    ALLOWED_LOGIN,
    ALLOWLIST_CONFIG,
    OUTSIDER_LOGIN,
    TEST_SPEC,
    make_pr,
)


class CommunitySweepSwitchTest(unittest.TestCase):
    def test_sweep_disabled_leaves_outsider_prs_alone(self) -> None:
        gh = FakeGitHubClient()
        gh.add_pr(make_pr(7, author=OUTSIDER_LOGIN))
        with patch.object(config, ALLOWLIST_CONFIG, (ALLOWED_LOGIN,)), \
             patch.object(config, "COMMUNITY_PR_SWEEP", False):
            community._sweep_community_contribution_prs(gh, TEST_SPEC)
        self.assertEqual(gh.pulls[7].labels, [])
        self.assertEqual(gh.posted_pr_comments, [])
