"""Rule-Based Automation Module (Mac Shortcuts style) for Knobu daemon."""

from __future__ import annotations

import threading

from knobu.modules.automation.engine import (
    ACTION_TYPES,
    CONDITION_TYPES,
    TRIGGER_TYPES,
    AutomationAction,
    AutomationLogEntry,
    AutomationRule,
    capture_snapshot,
    check_condition,
    evaluate_rule_trigger,
    load_history,
    load_rules,
    run_rule_now,
    save_rules,
)
from knobu.modules.base import Module

__all__ = [
    "AutomationModule",
    "AutomationRule",
    "AutomationAction",
    "AutomationLogEntry",
    "TRIGGER_TYPES",
    "CONDITION_TYPES",
    "ACTION_TYPES",
    "load_rules",
    "save_rules",
    "load_history",
    "run_rule_now",
]


class AutomationModule(Module):
    id = "automation"
    name = "Automations"
    description = "Rule-based triggers and actions (Wi-Fi, VPN, battery, apps, folders, and schedules)."
    icon = "system-run-symbolic"
    defaults = {
        "enabled": True,
        "poll_seconds": 5,
    }

    def run(self, stop: threading.Event) -> None:
        poll = max(2, int(self.settings.get("poll_seconds", 5)))
        rules = load_rules()
        folders = [r.trigger_value for r in rules if r.enabled and r.trigger_type == "folder_new_file" and r.trigger_value]
        prev = capture_snapshot(folders)

        while not stop.wait(poll):
            rules = load_rules()
            enabled_rules = [r for r in rules if r.enabled]
            if not enabled_rules:
                continue
            folders = [r.trigger_value for r in enabled_rules if r.trigger_type == "folder_new_file" and r.trigger_value]
            cur = capture_snapshot(folders)
            for rule in enabled_rules:
                try:
                    if evaluate_rule_trigger(rule, prev, cur) and check_condition(rule, cur):
                        ok, msg = run_rule_now(rule)
                        self.log.info("automation '%s' -> %s (%s)", rule.name, msg, "ok" if ok else "err")
                except Exception as err:
                    self.log.warning("automation '%s' failed: %s", rule.name, err)
            prev = cur
