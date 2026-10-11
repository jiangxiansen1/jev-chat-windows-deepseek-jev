# -*- coding: utf-8 -*-
"""慢车道侧栏：展示狗头军师的精简分析与话术，话术可一键填入微信（填入 ≠ 发送）。

三条约束：
  - 只认 core.advisor.ask_advisor 的返回契约，不感知 dsh 的任何细节；
  - 分析文本一律当**纯文本**渲染，不解析、不执行其中任何内容；
  - 默认收起，点「请教军师」才展开 —— 它只是第二意见，不该挤占快车道的界面。
"""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, PushButton

_IDLE_HINT = "点「请教军师」让狗头军师看一眼这局"
_BUSY_HINT = "军师正在看这段对话…"
_DONE_HINT = "军师看完了，话术可以直接填入（填入不会自动发送）"
_ERROR_HINTS = {
    "no-context": "还没读到聊天内容：微信窗口要可见、不要最小化，再点一次",
    "dsh-missing": "找不到 dsh 命令，慢车道暂时用不了；快车道那三条候选照常可用",
    "busy": "军师正在看上一段，稍等一下再点",
    "timeout": "军师超时了，快车道那三条照常用",
    "no-final": "军师这次没给出结论，快车道那三条照常用",
}


def _hint_for(error) -> str:
    key = str(error or "")
    return _ERROR_HINTS.get(key) or f"军师这次没能给出结论（{key or '未知原因'}）"


class AdvisorPanel(CardWidget):
    """悬浮窗内的可折叠侧栏。"""

    def __init__(self, on_fill=None, parent=None):
        super().__init__(parent)
        self.on_fill = on_fill
        self._candidates: list[str] = []
        self._buttons: list[QPushButton] = []
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        head = QHBoxLayout()
        head.addWidget(BodyLabel("狗头军师（慢车道）"), 1)
        self._toggle = PushButton("展开")
        self._toggle.clicked.connect(lambda: self.set_expanded(not self._expanded))
        head.addWidget(self._toggle)
        layout.addLayout(head)

        # 会话归属常驻显示：结果可能在你切到别的会话之后才回来，
        # 没有这一行就没法判断「这条建议是给谁的」
        self._chat_label = BodyLabel("")
        self._chat_label.setWordWrap(True)
        layout.addWidget(self._chat_label)

        self._status = BodyLabel(_IDLE_HINT)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # 分析与候选放在可折叠的 body 里
        self._body = QWidget()
        body = QVBoxLayout(self._body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)

        self._analysis = BodyLabel("")
        self._analysis.setWordWrap(True)
        body.addWidget(self._analysis)

        self._cand_box = QVBoxLayout()
        self._cand_box.setSpacing(6)
        body.addLayout(self._cand_box)

        layout.addWidget(self._body)
        self._body.setVisible(False)

    # --- 对外接口（core.advisor 的契约）-------------------------------------

    def set_busy(self, busy: bool) -> None:
        """慢车道正在跑：给个正在进行的提示，并禁用已有按钮防重复点。"""
        if busy:
            self._status.setText(_BUSY_HINT)
            self.set_expanded(True)
        for button in self._buttons:
            button.setEnabled(not busy)

    def set_result(self, result: dict) -> None:
        """渲染一次 ask_advisor 的返回。失败时**清掉上一次的候选**。"""
        data = result if isinstance(result, dict) else {}
        name = str(data.get("session_name") or "")
        self._chat_label.setText(f"会话：{name}" if name else "")
        if not data.get("ok"):
            # 清空旧候选：留着的话用户可能点到已经过期的建议
            self._candidates = []
            self._analysis.setText("")
            self._rebuild()
            self._status.setText(_hint_for(data.get("error")))
            self.set_expanded(True)
            return
        self._analysis.setText(str(data.get("analysis") or ""))
        self._candidates = [str(c) for c in (data.get("candidates") or []) if str(c).strip()]
        self._rebuild()
        self._status.setText(_DONE_HINT)
        self.set_expanded(True)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self._body.setVisible(self._expanded)
        self._toggle.setText("收起" if self._expanded else "展开")

    def clear(self) -> None:
        """清空面板。微信或界面切到别的会话时调用 —— 留着旧分析会被误用。"""
        self._candidates = []
        self._analysis.setText("")
        self._chat_label.setText("")
        self._rebuild()
        self._status.setText(_IDLE_HINT)
        self.set_expanded(False)

    def text(self) -> str:
        """当前可见文案（会话归属 + 状态 + 分析）。给测试用，也方便排查。"""
        parts = [self._chat_label.text(), self._status.text(), self._analysis.text()]
        return "\n".join(p for p in parts if p)

    def fill_button_count(self) -> int:
        return len(self._buttons)

    # --- 内部 --------------------------------------------------------------

    def _rebuild(self) -> None:
        """重建候选行：每条候选一行文字 + 一个「填入微信」。"""
        for button in self._buttons:
            button.setParent(None)
            button.deleteLater()
        self._buttons = []
        while self._cand_box.count():
            item = self._cand_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for text in self._candidates:
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            label = BodyLabel(text)
            label.setWordWrap(True)
            line.addWidget(label, 1)
            button = PushButton("填入微信")
            button.clicked.connect(lambda _checked=False, t=text: self._fill(t))
            line.addWidget(button)
            self._cand_box.addWidget(row)
            self._buttons.append(button)

    def _fill(self, text: str) -> None:
        if callable(self.on_fill):
            self.on_fill(text)
