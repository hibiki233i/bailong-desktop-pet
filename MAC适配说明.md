# macOS 适配说明

已在 Apple Silicon 实机验证：macOS 27.2、Python 3.13、PySide6 6.9.2。

## 从源码运行

项目根目录下执行：

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-macos.txt
.venv/bin/python app/pet.py
```

素材放在 `outputs/` 下，这个目录不进 Git：`白龙桌宠素材/` 是 Codex 形象，`Claude桌宠素材/` 是 Claude 形象。少一套时只显示另一只。运行状态和自检报告保存在 `~/Library/Application Support/BailongPet`。

自检：

```bash
.venv/bin/python app/pet.py --self-test
```

报告写到上面的用户数据目录。

## 打包

```bash
.venv/bin/python work/build_macos.py
```

生成 `dist-macos/BailongPet.app`。脚本按当前机器的架构构建，并做临时签名，只适合本机测试。发给别人前需要正式签名和公证。

两套素材现在都是 WebP，不需要 FFmpeg。如果换回 WebM 素材，脚本会把 `imageio-ffmpeg` 的静态 FFmpeg 放进 `.app`，不依赖 Homebrew。

## 对接 Codex

Codex 桌面应用已改名为 ChatGPT。程序按这个顺序查找 `codex`：

1. 环境变量 `BAILONG_CODEX`
2. `PATH`
3. `ChatGPT.app` 和旧的 `Codex.app` 内置的命令行程序
4. Homebrew 和 `~/.local/bin`

## 对接 Claude

程序只读这两处，不改 Claude 的任何设置，也不发模型请求：

- `~/.claude/sessions/<pid>.json`：每个运行中的会话的状态，`busy`、`idle` 或 `waiting`。同目录的 `.key` 文件不读。
- `~/.claude/projects/*/<sessionId>.jsonl`：只取公开回复文字和工具名称，不读思考过程、工具参数和工具输出。

只看交互会话和后台会话，`claude -p` 这类自动调用不算。可以用环境变量 `CLAUDE_CONFIG_DIR` 指向其他目录。

Claude 桌宠没有对话模式。

## Claude 额度

Claude Code 只把账户额度交给 statusLine 命令。在控制面板勾选 Claude 卡片上的“读取真实额度”后，会有两处改动：

- 在 `~/Library/Application Support/BailongPet/` 放一个小脚本，它把 `rate_limits` 存成 `claude_limits.json`。
- 在 `~/.claude/settings.json` 加一项 `statusLine`，其他设置不变。

已经有自定义状态栏时不会覆盖。取消勾选时只删除这一项和上面两个文件。

使用前要知道：

- 只有用 claude.ai 订阅登录的会话才有 `rate_limits`。通过 `ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN` 或 API Key 使用时，Claude Code 不提供这项数据。
- 终端里的 Claude Code 会运行 statusLine。修改设置时已经打开的桌面应用会话没有运行它，新开的桌面会话还没验证。
- 配置后，Claude Code 底部的部分按键提示（比如 `esc to interrupt`）不再显示，这一行改成模型名和剩余额度。
- 额度在 Claude Code 收到回复时更新，所以气泡会显示数据更新时间。多个会话同时运行时，以最后写入的为准。

没有额度数据时，“查额度”显示本机记录里的 token 数，不是账户剩余额度。

## 控制面板

右键桌宠或点菜单栏图标，选“控制面板…”。可以看两边的状态和进行中的任务，分别控制显示、走动、气泡、音效和大小。桌宠已经在运行时，再次打开 `.app` 也会弹出面板。

## 自动启动

在控制面板或右键菜单里勾选“随 ChatGPT 或 Claude 自动启动”。它会创建 `~/Library/LaunchAgents/com.bailongpet.autostart.plist`，登录后在后台等待，这两个桌面应用打开时启动桌宠。

这个文件记录的是程序的绝对路径，移动项目或 `.app` 后要关掉再重新勾选。

## 和 Windows 的差异

- 没有 Dock 图标，入口在菜单栏。
- 桌宠窗口没有系统阴影，和 Windows 外观一致。对话气泡和输入框保留系统阴影。

## 内存

帧解压后每帧占 1 MiB（Retina，512 像素）。每只桌宠只常驻默认待机，其他动作播放时才在后台线程解码，并只留很少的缓存。解码速度约是播放速度的 13 倍，首帧在 15 毫秒内出现。

| 场景 | 改动前 | 现在 |
| --- | --- | --- |
| 单只 Codex 启动 | 15.5 秒 | 0.5 秒 |
| 单只 Codex 空闲占用 | 约 4.5 GiB | 188 MiB |
| 两只同时空闲 | 没有这个场景 | 约 295 MiB |
| 两只把全部动作循环 5 轮 | 没有这个场景 | 稳定在约 600 MiB，不再增长 |

这里的占用是活动监视器里的“内存”一栏。macOS 不会马上收回释放掉的 1 MiB 内存块，所以播放过很多动作后，数字会高于实际在用的量，但会停在一个上限。打包版实测在 290 到 520 MiB 之间，打开控制面板时偏高。

## 重新生成素材

- Codex 抠图：原始 WebM 放在 `outputs/白龙原始素材/`，运行 `python3 work/codex_matte/build.py`。
- Claude 动作：姿势图放在 `outputs/Claude素材源/raw/`，运行 `python3 work/claude_assets/build_clips.py`。需要新姿势时用 `gen.py` 通过本机图片桥生成。

这两个工具需要 numpy 和 scipy，运行桌宠本身不需要。

## 已实机验证

- 透明窗口，切换到其他应用后不消失，隐藏后可以恢复
- `.app` 打包、签名校验和打包后的自检，WebP 和 WebM 素材都验证过
- 从最小 `PATH` 环境读取真实额度，读取真实任务记录
- LaunchAgent 启动桌宠，关闭后不留文件
- 两只桌宠同时显示，切换到 Finder 后仍在屏幕上，退出后不留进程
- 读取真实的 Claude Code 会话：Claude 桌宠进入工作状态，控制面板显示任务名
- 桌宠运行时再次打开 `.app`，只有一个进程，控制面板弹出
- 使用两套完整素材时，全部 137 项测试通过

使用较少的素材时，依赖完整素材的测试会被跳过。

## 尚未验证

- 真实全屏时自动隐藏，以及切换 Space 和多显示器
- 发送真实对话
- 手动拖动、点击菜单栏和音效
- 真实会话进入等待确认状态（只用单元测试和模拟流程验证过）
- 从 claude.ai 订阅会话收到真实的 `rate_limits`（只用文档里的数据格式验证过）
- Claude 和 Codex 同时真实工作
- Intel Mac 和其他 macOS 版本
