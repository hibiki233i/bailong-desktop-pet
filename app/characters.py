"""The pets this app can show. Each one watches a single coding agent."""
from dataclasses import dataclass
from typing import Optional


def codex_quota(cancel):
    from quota import quota_windows, read_quota
    return quota_windows(read_quota(cancel=cancel))


def claude_usage(cancel):
    from claude_limits import limit_windows, magpie_windows
    from claude_status import usage_windows
    return magpie_windows() or limit_windows() or usage_windows(cancel=cancel)


def codex_sync(pet):
    from desktop_task_sync import DesktopTaskSync
    return DesktopTaskSync(pet)


def claude_sync(pet):
    from claude_status import ClaudeTaskSync
    return ClaudeTaskSync(pet)


@dataclass(frozen=True)
class Character:
    id: str
    agent: str
    title: str
    assets: str
    settings_group: str
    accent: str
    quota_title: str
    home_offset: int
    chat: bool
    read_quota: object
    make_sync: object
    loading: Optional[str] = None
    usage_title: str = ''
    real_limits: bool = False


CODEX = Character(id='codex', agent='Codex', title='白龙娘', assets='outputs/白龙桌宠素材', settings_group='', accent='#7b68c8',
                  quota_title='Codex 剩余额度', home_offset=0, chat=True,
                  read_quota=codex_quota, make_sync=codex_sync)
CLAUDE = Character(id='claude', agent='Claude', title='小克', assets='outputs/Claude桌宠素材', settings_group='claude', accent='#c96442',
                   quota_title='Claude 剩余额度', usage_title='Claude 本机用量', home_offset=290, chat=False,
                   read_quota=claude_usage, make_sync=claude_sync, real_limits=True)
CHARACTERS = (CLAUDE, CODEX)
