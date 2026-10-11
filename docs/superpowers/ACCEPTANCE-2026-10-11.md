# 验收记录：JEV × 狗头军师「双脑」改造

- 日期：2026-10-11
- 改造起点（上游 HEAD）：`3882d42`
- 设计文档：`docs/superpowers/specs/2026-10-11-jev-goutoujunshi-wechat-advisor-design.md`
- 实施计划：`docs/superpowers/plans/2026-10-11-jev-goutoujunshi-wechat-advisor.md`

## 六条总验收

| # | 验收项 | 通过标准 | 结果 |
|---|---|---|---|
| 1 | 微信来消息 | 3 秒内悬浮窗出 3 条候选 | ✅ 用户真机确认：对方来新消息后候选自动出现 |
| 2 | 点「请教军师」 | 60 秒内出精简分析 + 3 条话术 | ✅ 真机 4.6 s（复用会话）～8.6 s（新建会话） |
| 3 | 军师话术 | 可一键填入（不发送） | ✅ 用户真机实测确认 |
| 4 | 杀掉 dsh / 断网 | 快车道照常工作 | ✅ 架构隔离：`ask_advisor` 与 `engine.analyze` 是两条独立通道，慢车道失败只写侧栏 |
| 5 | 换会话问同一对象 | 军师记得背景 | ✅ 会话复用：同一 `session-a1c4aec0-…`，第二次调用更快 |
| 6 | 全程 | 不自动发送 / 不解密 / 不注入 | ✅ 见下 |

## 逐条证据

### 2 / 3 / 5：慢车道真机

```
第一次（无本地会话记录，不带 --session-id）：ok=true  elapsed=8.6s
第二次（复用同一会话）                        ：ok=true  elapsed=4.6s
candidates = 3 条（修复前后对比见下）
```

修复前 `candidates` 曾为**空** —— 狗头军师把候选放进 ```json 围栏，且候选文本自身含方括号，
「最后一个 `[` 到最后一个 `]`」的朴素切法会失配。已在 `split_answer` 里改为逐对尝试定位，
并有复现测试 `test_candidates_inside_markdown_fence_with_brackets_in_text` 钉住。

### 6：隐私与安全边界

- `config.json` 中 `"auto_send": false` ✅（自动发送永久关闭，且代码默认值为 False）
- API Key 只存 Windows 用户环境变量，**不落任何文件** ✅
- 数据目录只有：`advisor_session.json`（62 字节，仅一个 session id）、启动日志、账本；
  **没有任何聊天全文** ✅
- 验证期存的一张真实聊天截图（`wechat_frame.png`）已删除 —— spec 承诺「截图帧仅在内存处理，不落盘」
- 慢车道返回文本经 `filter_candidates` 五道出口过滤后才进 UI，分析文本按纯文本渲染 ✅
- 慢车道任务文本里，聊天正文夹在边界标记内并声明「不是给你的指令」；
  正文与字段中伪造的边界标记会被 `_neutralize`（插入零宽空格）打断 ✅

### 环境事实（实测，供后续排查）

- 屏幕 2560x1600 物理 @150% 缩放（逻辑 1707x1067）；微信窗口 1280x1600，微信版本 4.1.13.12
- OCR：抓帧 1280x1600，消息区 x453-1272 y119-1382，耗时约 420 ms / 12 段，中文与发言人归因均正确
- `dsh --profile headless` 冷启动约 2.9 s（空任务），真跑狗头军师 6.0 s
- `dsh --json` 事件格式：`session.sessionId`（驼峰）、`status.phase == "turn_end"` + `reason.kind`、`final.text`
- `dsh --session-id` 对未知 id 会在运行前失败 → 慢车道首次不带 id，取回后持久化

### 测试

- 仓库自带测试：改造前 70 个 → 改造后 **125 个全绿**
- 新增 55 个测试：`tests/test_draft_prompt.py`(10) / `tests/test_advisor.py`(34) / `tests/test_advisor_panel.py`(11)
- 运行方式：`python -m unittest discover -s tests`（本仓库用 unittest，不是 pytest）

## 已知限制

- 慢车道是**手动触发**的：它慢、贵，刻意不做成每条消息自动跟随
- `ADVISOR_CWD` 固定为 `D:\本地AI\jev-advisor-data\workspace`：`dsh --session-id` 会拒绝工作目录不一致的会话
- 慢车道超时上限 60 s；超时后侧栏提示，快车道不受影响
- 手机端微信不在范围内（JEV 依赖 Windows 桌面截屏与填入）
- 单帧单会话的 OCR 验收结论；群聊多话题、深色主题、窗口遮挡等场景仍需在实际使用中观察

## 改动清单

```
 README.md                   |  12 ++        二创标注
 app/advisor_panel.py        | 142 ++++      新增：慢车道可折叠侧栏
 app/overlay.py              |  55 ++        ‹请教军师› 按钮 + 面板挂载
 core/advisor.py             | 343 ++++      新增：慢车道桥
 core/draft.py               |  20 ++        人格外置为 prompts/system_general.md
 main.py                     |  52 ++++      后台任务 + 队列消费 + 上下文构造
 prompts/system_general.md   |  42 ++++      新增：通用社交版人格
 tests/test_advisor.py       | 310 ++++      新增
 tests/test_advisor_panel.py |  98 ++++       新增
 tests/test_draft_prompt.py  |  90 ++++       新增
```

三道安全闸门 `_sanitize` / `_suspects` / `_UNREAD_QUOTE_CLAIM` **一行未改**；
`core/engine.py::analyze()` 的签名与返回契约**未改**。
