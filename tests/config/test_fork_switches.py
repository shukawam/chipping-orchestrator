# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Configuration behavior of the fork's opt-in settings."""

import itertools
import unittest

from tests.config import config_reload_helpers as _reload

_TRUTHY_SPELLINGS = ("on", "ON", " on ", "1", "true", "True", "yes")
# Default-off boolean switches: the fork's opt-in behaviors, each off unless
# an operator names it, and parsed by the same strict truthy set.
_DEFAULT_OFF_SWITCHES = ("OPEN_PR_AS_DRAFT",)


class PickupLabelConfigTest(unittest.TestCase):
    """PICKUP_LABEL is off (empty) unless named, and is read without the
    whitespace an operator's `.env` may carry around it."""

    def test_default_is_empty(self) -> None:
        config = _reload.load_config()
        self.assertEqual(config.PICKUP_LABEL, "")

    def test_value_is_stripped(self) -> None:
        config = _reload.load_config({"PICKUP_LABEL": "  agent-ready "})
        self.assertEqual(config.PICKUP_LABEL, "agent-ready")


class DefaultOffSwitchConfigTest(unittest.TestCase):
    def test_default_is_off(self) -> None:
        config = _reload.load_config()
        for switch in _DEFAULT_OFF_SWITCHES:
            with self.subTest(switch=switch):
                self.assertFalse(getattr(config, switch))

    def test_truthy_spellings_turn_on(self) -> None:
        for switch, spelling in itertools.product(_DEFAULT_OFF_SWITCHES, _TRUTHY_SPELLINGS):
            with self.subTest(switch=switch, value=spelling):
                config = _reload.load_config({switch: spelling})
                self.assertTrue(getattr(config, switch))


class DefaultOnSwitchConfigTest(unittest.TestCase):
    """COMMUNITY_PR_SWEEP keeps the upstream sweep unless explicitly turned off."""

    def test_community_pr_sweep_default_is_on(self) -> None:
        self.assertTrue(_reload.load_config().COMMUNITY_PR_SWEEP)

    def test_community_pr_sweep_off_disables(self) -> None:
        self.assertFalse(_reload.load_config({"COMMUNITY_PR_SWEEP": "off"}).COMMUNITY_PR_SWEEP)
