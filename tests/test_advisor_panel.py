# -*- coding: utf-8 -*-
"""AdvisorPanel 的逻辑层测试：文案、按钮数量、忙态、填入回调。

只测可测的东西 —— 不测像素和外观。用 Qt 的 offscreen 平台跑，
不需要真实显示器（无头/CI 也能跑）。

注意：必须先把 QT_QPA_PLATFORM 设好再 import PySide6，
且在造控件前先有 QApplication 实例。
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

_app = None


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication([])


def _fill_buttons(panel):
    """面板里所有「填入微信」按钮，按创建顺序。"""
    return [b for b in panel.findChildren(QPushButton) if "填入" in b.text()]


class AdvisorPanelTests(unittest.TestCase):
    def _panel(self, on_fill=None):
        from app.advisor_panel import AdvisorPanel
        return AdvisorPanel(on_fill=on_fill)

    def test_starts_with_prompt_so_user_knows_what_the_button_does(self):
        panel = self._panel()
        self.assertIn("请教军师", panel.text())
        self.assertEqual(panel.fill_button_count(), 0)

    def test_timeout_shows_human_hint_not_a_stack_trace(self):
        panel = self._panel()
        panel.set_result({"ok": False, "error": "timeout"})
        self.assertIn("超时", panel.text())

    def test_dsh_missing_shows_human_hint(self):
        panel = self._panel()
        panel.set_result({"ok": False, "error": "dsh-missing"})
        self.assertIn("dsh", panel.text().lower())

    def test_no_context_tells_user_to_keep_wechat_visible(self):
        panel = self._panel()
        panel.set_result({"ok": False, "error": "no-context"})
        self.assertIn("微信", panel.text())

    def test_unknown_error_still_renders_something(self):
        panel = self._panel()
        panel.set_result({"ok": False, "error": "run-failed"})
        self.assertTrue(panel.text().strip())

    def test_renders_analysis_text(self):
        panel = self._panel()
        panel.set_result({"ok": True, "analysis": "她的意图是试探", "candidates": []})
        self.assertIn("她的意图是试探", panel.text())

    def test_one_fill_button_per_candidate(self):
        panel = self._panel()
        panel.set_result({"ok": True, "analysis": "A", "candidates": ["一", "二", "三"]})
        self.assertEqual(panel.fill_button_count(), 3)
        self.assertEqual(len(_fill_buttons(panel)), 3)

    def test_no_candidates_means_no_fill_buttons(self):
        panel = self._panel()
        panel.set_result({"ok": True, "analysis": "只有分析", "candidates": []})
        self.assertEqual(panel.fill_button_count(), 0)

    def test_busy_state_tells_user_advisor_is_working(self):
        panel = self._panel()
        panel.set_busy(True)
        self.assertIn("正在看", panel.text())
        panel.set_busy(False)

    def test_fill_callback_gets_the_candidate_text(self):
        got = []
        panel = self._panel(on_fill=got.append)
        panel.set_result({"ok": True, "analysis": "A", "candidates": ["甲", "乙"]})
        _fill_buttons(panel)[1].click()
        self.assertEqual(got, ["乙"])

    def test_failure_result_clears_previous_candidates(self):
        # 上一次的候选不能留在面板上：用户可能点到已经过期的建议
        panel = self._panel()
        panel.set_result({"ok": True, "analysis": "A", "candidates": ["甲"]})
        panel.set_result({"ok": False, "error": "timeout"})
        self.assertEqual(panel.fill_button_count(), 0)


if __name__ == "__main__":
    unittest.main()
