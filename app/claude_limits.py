"""Real Claude limits, from Magpie when it holds the login, or else from a statusLine command."""
import http.client
import json
import os
import shlex
import stat
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from claude_status import claude_home
from platform_support import user_data

SUPPORTED = sys.platform == 'darwin'
SCRIPT_NAME = 'claude_statusline.sh'
LIMITS_NAME = 'claude_limits.json'
WINDOWS = (('five_hour', '5小时'), ('seven_day', '一周'))
MAGPIE_QUOTAS = 'http://127.0.0.1:3425/v1/magpie/quotas'
MAGPIE_WINDOWS = {'5 hours': '5小时', '7 days': '一周'}

# A session reports no rate_limits before its first reply, so that input must not replace saved data.
# jq keeps only the limits. Without jq the whole input is saved, and the pet still reads only the limits.
SCRIPT = r"""#!/bin/sh
# Written by AI 桌宠. Saves Claude's rate limits for the pet and prints a short status line.
input=$(cat)
dir=$(dirname "$0")
case "$input" in
*'"rate_limits"'*)
    tmp="$dir/claude_limits.$$"
    (
        umask 077
        printf '%s' "$input" | jq -c '{rate_limits}' > "$tmp" 2>/dev/null || printf '%s' "$input" > "$tmp"
    )
    mv -f "$tmp" "$dir/claude_limits.json"
    ;;
esac
printf '%s' "$input" | jq -r '[.model.display_name, (.rate_limits.five_hour.used_percentage // empty | "5 小时剩 \(100 - . | floor)%"), (.rate_limits.seven_day.used_percentage // empty | "7 天剩 \(100 - . | floor)%")] | map(select(.)) | join(" · ")' 2>/dev/null
exit 0
"""


def age(seconds):
    minutes = int(seconds // 60)
    if minutes < 1:
        return '刚刚'
    if minutes < 60:
        return f'{minutes} 分钟前'
    hours = minutes // 60
    return f'{hours} 小时前' if hours < 48 else f'{hours // 24} 天前'


def window_row(name, used, resets, now):
    if used is None or (resets and resets <= now):
        return {'name': name, 'text': '已重置，等待下次更新'}
    return {'name': name, 'remaining': max(0, min(100, 100 - float(used))), 'resetsAt': resets}


def finish_rows(rows, saved, now):
    """None when nothing is current, so the caller moves on to the next source."""
    if not any('remaining' in row for row in rows):
        return None
    if saved:
        rows.append({'name': '更新', 'text': age(now - saved)})
    return rows


def read_magpie(url=MAGPIE_QUOTAS, timeout=2):
    """Magpie's quota report, or None while it is not running. A system proxy must not catch this local call."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=timeout) as response:
            return json.load(response)
    except (OSError, ValueError, http.client.HTTPException):
        return None


def stamp(text):
    try:
        return datetime.fromisoformat(text).timestamp()
    except (TypeError, ValueError):
        return None


def magpie_windows(provider='claude', report=None, now=None):
    """Rows from Magpie, which holds the login when Claude Code runs through it. The account email stays unread."""
    report = read_magpie() if report is None else report
    entries = report.get('data') if isinstance(report, dict) else None
    if not isinstance(entries, list):
        return None
    entries = [entry for entry in entries if isinstance(entry, dict) and entry.get('provider') == provider]
    if not entries:
        return None
    entry = next((item for item in entries if item.get('last')), entries[0])
    windows = entry.get('windows')
    if not isinstance(windows, list):
        return None
    now = now or time.time()
    rows = []
    for window in windows:
        used = window.get('used') if isinstance(window, dict) else None
        if isinstance(used, (int, float)):
            rows.append(window_row(MAGPIE_WINDOWS.get(window.get('name'), str(window.get('name'))), used, stamp(window.get('resetsAt')), now))
    return finish_rows(rows, stamp(entry.get('readAt')), now)


def limit_windows(path=None, now=None):
    """Rows for the quota bubble, or None when there is no usable report yet."""
    path = Path(path or user_data() / LIMITS_NAME)
    try:
        saved = path.stat().st_mtime
        limits = json.loads(path.read_text(encoding='utf-8'))['rate_limits']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(limits, dict):
        return None
    now = now or time.time()
    rows = []
    for key, name in WINDOWS:
        window = limits.get(key)
        window = window if isinstance(window, dict) else {}
        rows.append(window_row(name, window.get('used_percentage'), window.get('resets_at'), now))
    return finish_rows(rows, saved, now)


def command():
    return shlex.quote(str(user_data() / SCRIPT_NAME))


def settings_path(home=None):
    return claude_home(home) / 'settings.json'


def read_settings(home=None):
    path = settings_path(home)
    try:
        settings = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise RuntimeError(f'读不了 {path.name}，所以没有改动：{error}') from error
    if not isinstance(settings, dict):
        raise RuntimeError(f'{path.name} 的格式不对，所以没有改动。')
    return settings


def write_settings(settings, home=None):
    """Replace the file in one step, so a running Claude Code never reads half of it."""
    path = settings_path(home).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix='.settings.', suffix='.tmp')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as target:
            json.dump(settings, target, ensure_ascii=False, indent=2)
            target.write('\n')
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def enabled(home=None):
    try:
        line = read_settings(home).get('statusLine')
    except RuntimeError:
        return False
    return isinstance(line, dict) and line.get('command') == command()


def enable(home=None):
    settings = read_settings(home)
    if settings.get('statusLine') and not enabled(home):
        raise RuntimeError('Claude Code 里已经有自定义状态栏，所以没有改动。')
    folder = user_data()
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / SCRIPT_NAME
    script.write_text(SCRIPT, encoding='utf-8')
    script.chmod(0o755)
    settings['statusLine'] = {'type': 'command', 'command': command()}
    write_settings(settings, home)


def disable(home=None):
    """Remove only what enable added. Someone else's status line stays."""
    if not enabled(home):
        return
    settings = read_settings(home)
    del settings['statusLine']
    write_settings(settings, home)
    for name in (SCRIPT_NAME, LIMITS_NAME):
        (user_data() / name).unlink(missing_ok=True)
