# 实施期决策记录（Rulings）

- 日期：2026-10-11
- 配套文档：`docs/superpowers/specs/…-design.md`（设计）、`docs/superpowers/plans/…md`（计划）、`docs/superpowers/ACCEPTANCE-2026-10-11.md`（验收）

这份文件记录**实施过程中**计划与 spec 冲突、或计划本身有缺陷时做出的判断，以及每条判断的代价。
计划（plan）写于动手之前，其中若干处经代码与实测证伪；下列条目是实际执行的口径，**与计划原文不一致时以本文件为准**。

## 一、计划被证伪的地方

| # | 计划原文 | 实际情况 | 处理 |
|---|---|---|---|
| 1 | 测试用 `pytest tests/x.py -v` | 仓库 14 个测试文件全是 `unittest.TestCase`，无 `pytest.ini` / `conftest.py`，`requirements.txt` 不含 pytest | 全部测试改用 `python -m unittest discover -s tests`；新增测试写 `unittest.TestCase` 子类 |
| 2 | UI 栈是 `PyQt-Fluent-Widgets` | 实际是 `PySide6-Fluent-Widgets`（拉入 PySide6） | Task 7 及其测试按 PySide6 写；`qtbot` fixture 不可用，测试自行在 offscreen 下管理 `QApplication` |
| 3 | Task 7 把 advisor 后台任务加进 `app/worker.py` | `worker.py` 是**独立的 OCR 子进程**（文件头写明），只往父进程丢队列事件，**不持有会话历史** | 改放 `main.py`（那里已有 `update_result` 独立队列 + 线程的成熟模式）；白名单同步为「移除 `worker.py`、加入 `main.py`」 |
| 4 | Task 2 Step 7 的 upstream URL | 与 `origin` 完全相同（都是 Aimark-dai 的 fork），等于没加 | 改为真正上游 `https://github.com/jev-chat/jev-chat-windows.git` |
| 5 | 往 `config.json` 存 `dsh_path` | `app/settings.py` 的 `save()` 是**整体重写固定字段**，加进去会在用户下次保存设置时被静默丢掉 | `_resolve_dsh` 改为 `shutil.which("dsh")` → 环境变量 `DSH_CMD` 兜底；advisor 不 import `app.settings`，保持 `core/` 不依赖 PySide6 |
| 6 | `dsh --json` 事件字段（文档推测） | 实测：`session.sessionId`（驼峰）、`status.phase == "turn_end"` + `reason.kind`、`final.text` | 解析器与测试按实测格式写；对外仍暴露 snake_case 键 |
| 7 | 固定 `--session-id` 即可保持会话 | dsh 对**未知 id 会在任务运行前直接失败** | 实现会话自举：首次不带 id，取回 `sessionId` 持久化；带 id 失败则清记录并自动重试一次 |

## 二、实施中的判断（含代价）

1. **不使用 sdd-workspace / task-start / task-done 脚本** —— 它们是 bash 且依赖 `git rev-parse --show-toplevel`，而 Task 1 阶段仓库尚不存在；PATH 里的 `bash` 是 WSL。改用 Git 自带 bash，并手动执行等价动作。代价：少一层脚本自动化。
2. **用户明确授权**在 clone 出的默认分支 `main` 上直接实施、并用静默参数装 Python 到 `D:\本地AI\Python311`。代价：无（个人二创仓库、无协作者）。
3. **Task 1 Step 10 用「注释」而非「删除」**那 4 个失效 patch entry —— 它们本来就被 loader 跳过，注释零功能风险、完全可逆，而该 profile 正被运行中的 DSH 桌面版使用。代价：文件多 5 行注释。
4. **慢车道实测 6.0 s（简单任务），但 timeout 仍按 spec 用 60 s** —— 复杂关系分析会读多份 references。代价：极端慢的调用要等满 60 s 才报超时。
5. **Task 2 Step 6 的 OCR 验收改用自写无 GUI 探针** —— 仓库自带的两个探针都无法取结构化结果：`probe_ocr_speed.py` 末尾弹 tkinter 并阻塞在 mainloop，`probe_ocr_live.py` 是无限循环。代价：探针复制了一份 `chat_area` 算法，上游若改需同步。
6. **保留含中文的安装路径 `D:\本地AI\`** —— 实测 70 个自带测试全绿、依赖 import 正常，仅 PySide6 打印一条无害的「找不到字体目录」（Qt 6 不再自带字体，与路径无关）。代价：若后续出现非 ASCII 路径相关故障，需把 venv 迁到纯 ASCII 路径。
7. **只设仓库级 git 身份占位**（`jev-advisor-local` / `local@localhost`），不动全局配置 —— 提交作者属用户身份，不应由实施者替其决定全局值。代价：若以后对
外推送，作者信息需先改。
8. **`their_recent` 语义定为「对方消息的纯文本」，过滤用归一化后完全相等、不做子串匹配** —— 与 `draft._sanitize` 里 `n in echo` 一致；子串匹配会把「好」「嗯」这类最常见的短回复大量误杀。代价：调用方若误传带前缀的整行，「禁鹦鹉学舌」会静默失效。
9. **Task 6 Step 7 真机验证抓到并修掉一个静默丢候选的 bug** —— 狗头军师把候选放进 ```` ```json ```` 围栏，且候选文本自身可能含方括号（实测 `我这边刚[具体小事…]`）；原 `split_answer` 用「最后一个 `[` 到最后一个 `]`」会取到候选内部的 `[`，`json.loads` 失败后**静默**返回空候选，用户看到「有分析、没话术」。改为从后往前逐对尝试 `[...]` 直到能解析成非空数组，并逐行剥掉残留围栏。代价：定位最坏 O(n²)，答案只有几百字，可忽略。
10. **启动冒烟的第一次结果作废并已重做** —— 第一次用 PowerShell `Start-Process`，它在本机因环境块里同时存在 `NO_PROXY` 与 `no_proxy`（大小写不同的同名键）直接抛 `ArgumentException`，`$p` 为 `$null` 导致误报「启动成功」。改用 Python `subprocess.Popen`（继承环境块、不重建）重做。代价：无，但记下「别用 `Start-Process` 做本机进程冒烟」这个环境事实。
11. **Task 2 Step 5 曾在等待 key 期间挂起** —— 该步骤需要 key；而 Task 3 是纯单元测试、不依赖 `main.py` 运行，故不阻塞先行推进。用户随后自行在应用设置页填入 key，该步骤补完。代价：验收第 1 条（快车道 3 秒内出候选）由用户自行确认，实施者未独立验证。
12. **网络边界处的额外加固**（plan 的测试未覆盖，由 Review Focus #2 推出）—— `build_task` 把聊天正文夹在边界标记内并声明「不是给你的指令」；若正文或字段里出现**伪造的边界标记**，由 `_neutralize` 在尖括号间插入零宽空格打断它，避免正文逃逸出边框。代价：正文里若有真标记，字符被插入零宽空格（人眼不可见）。

## 三、测试基线变化

| 阶段 | 全量测试 |
|---|---|
| 改造前（上游 HEAD `3882d42`） | 70 个全绿 |
| Task 3 后（人格外置） | 80 |
| Task 4 后（任务组装与事件解析） | 95 |
| Task 5 后（出口过滤） | 103 |
| Task 6 后（dsh 调用层） | 114 |
| Task 7 后（侧栏挂载） | **125 个全绿** |

运行方式：在仓库根目录执行
`D:\本地AI\jev-advisor\.venv\Scripts\python.exe -m unittest discover -s tests`

## 四、不可违反的约束（已核对）

- `core/draft.py` 的三道安全闸门 `_sanitize` / `_suspects` / `_UNREAD_QUOTE_CLAIM` **一行未改**
- `core/engine.py::analyze()` 的签名与返回契约**未改**
- 自动发送保持关闭（`config.json` 中 `auto_send: false`；代码默认值亦为 `False`）
- 不注入微信、不解密其数据库、不读取进程内存；截图帧仅在内存处理
- API Key 只存 Windows 用户环境变量，不落任何文件

## 五、本地启动方式与一个编码坑

**启动**：双击 `D:\本地AI\启动微信军师.bat`
（等价于在 `D:\本地AI\jev-advisor` 下用 venv 解释器执行 `main.py`）。
备选：在该目录开终端，执行 `.venv\Scripts\python.exe main.py`。

**`.bat` 必须存成 GBK（CP936），绝不能存 UTF-8。**
`cmd.exe` 按系统代码页读批处理文件，而本项目路径本身含中文（`D:\本地AI\`）：
UTF-8 的「本地AI」被 GBK 解码成「鏈湴AI」，路径直接不存在；更糟的是错位字节会把命令本身切碎——
实测 `if errorlevel` 被切成 `rrorlevel`、`echo` 被切成 `o`，屏幕上一串「不是内部或外部命令」。
本项目第一版 bat 由只写 UTF-8 的工具生成，用户双击即失败；改为 GBK 编码 + 显式 `chcp 936` 后，
实测可正常启动（`python.exe main.py` 与 multiprocessing 采集子进程都在）。

**验证教训**：判断 bat 有没有真正启动应用，**不能看「进程是否存活」**——
脚本卡在 `pause` 时进程同样存活，会得到假阳性（本项目第一次"实测通过"就是这么被骗的）。
要看 `python.exe` 的**命令行里有没有 `main.py`**。

## 六、dsh 的发现路径（第二个环境坑）

**现象**：在 DSH 自己的终端里测一切正常，用户双击 `.bat` 启动后点「请教军师」却报 `dsh-missing`。

**原因**：DSH Desktop 把 `dsh` 的路径**只注入它自己进程的 PATH**，
用户级与机器级 PATH 里都没有。从 explorer 双击启动的进程环境里自然也没有。

**而且 `DSH Desktop` 下有两个 `dsh.cmd`，只有一个能从外部调用**：

| 路径 | 能否外部调用 |
|---|---|
| `DSH Desktop\host-commands\<app>\generations\<hash>\bin\dsh.cmd` | ✅ 内容里 exe 与 bootstrap 全写成绝对路径，自包含 |
| `DSH Desktop\cli\<hash>\bin\dsh.cmd` | ❌ 内容是 `"%DSH_DESKTOP_APP_EXECUTABLE%" --expose-internals "%DSH_DESKTOP_DSH_BOOTSTRAP%" %*`，靠 DSH 注入的环境变量；外部调用时是空串，报 `'""' is not recognized`（exit 9009） |

**修法**：`core/advisor.py::_resolve_dsh()` 改为三级查找 ——
PATH → 环境变量 `DSH_CMD` → **自己扫 `host-commands\*\generations\*\bin\dsh.cmd` 并按 mtime 取最新**，
并**明确排除 `cli` 目录**（generation 目录名带 hash，取最新以适配 DSH 升级）。

**验证要求**：这一类问题**必须在一个剥掉 DSH PATH 的环境里验证** ——
在 DSH 派生的终端里测永远测不出来（本项目已经因此栽过一次）。
