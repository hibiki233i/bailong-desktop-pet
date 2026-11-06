"""Read-only observer of Claude Code. No model requests and no settings changes.

Each running session keeps ~/.claude/sessions/<pid>.json current with status
busy, idle or waiting. Transcripts add what was said. Only public text and tool
names are read here, never thinking, tool arguments or tool output, and the .key
files beside the session records are left alone.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import time

import psutil
from PySide6.QtCore import QObject, QTimer

WATCHED_KINDS = {'interactive', 'background'}
TAIL_BYTES = 4 << 20
STEPS = {'Bash': '正在执行操作', 'Edit': '正在修改文件', 'Write': '正在修改文件', 'NotebookEdit': '正在修改文件', 'Read': '正在查阅文件',
         'Grep': '正在查阅文件', 'Glob': '正在查阅文件', 'WebSearch': '正在查阅资料', 'WebFetch': '正在查阅资料', 'Agent': '正在安排子任务'}


def claude_home(home=None):
    return Path(home or os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')


def process_alive(pid, started):
    """A crashed session leaves its file behind, and the pid may since belong to something else."""
    try:
        created = psutil.Process(pid).create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False
    try:
        # procStart is written in UTC.
        return abs(datetime.strptime(' '.join(str(started).split()), '%a %b %d %H:%M:%S %Y').replace(tzinfo=timezone.utc).timestamp() - created) < 5
    except ValueError:
        return True


def public_events(record):
    """Return (texts, tool names) from one transcript record, leaving everything private behind."""
    message = record.get('message')
    if record.get('type') != 'assistant' or record.get('isSidechain') or not isinstance(message, dict):
        return [], []
    texts, tools = [], []
    for block in message.get('content') or []:
        if isinstance(block, dict) and block.get('type') == 'text' and str(block.get('text') or '').strip():
            texts.append(str(block['text']).strip())
        elif isinstance(block, dict) and block.get('type') == 'tool_use':
            tools.append(str(block.get('name') or ''))
    return texts, tools


class TranscriptTail:
    """Follow one transcript, reading only the bytes added since the last look."""

    def __init__(self, path):
        self.path = Path(path)
        self.offset = None
        self.partial = b''
        self.text = ''
        self.step = ''

    def update(self):
        try:
            size = self.path.stat().st_size
            if self.offset is None or size < self.offset:
                self.offset = max(0, size - TAIL_BYTES)
                self.partial = b''
            if size == self.offset:
                return
            with self.path.open('rb') as source:
                source.seek(self.offset)
                data = self.partial + source.read(size - self.offset)
            self.offset = size
        except OSError:
            return
        lines = data.split(b'\n')
        self.partial = lines.pop()
        for line in lines:
            # Most lines are large request logs, so skip them before parsing.
            if b'"assistant"' not in line:
                continue
            try:
                texts, tools = public_events(json.loads(line))
            except ValueError:
                continue
            if texts:
                self.text = texts[-1]
                self.step = ''
            if tools:
                self.step = STEPS.get(tools[-1], '正在调用工具')


class ClaudeTaskReader:
    def __init__(self, home=None, alive=process_alive):
        self.home = claude_home(home)
        self.alive = alive
        self.tails = {}

    def available(self):
        return (self.home / 'sessions').is_dir()

    def transcript(self, session):
        known = self.tails.get(session)
        if known is None:
            found = next(iter((self.home / 'projects').glob(f'*/{session}.jsonl')), None)
            if found is None:
                return None
            known = self.tails[session] = TranscriptTail(found)
        known.update()
        return known

    def sessions(self):
        rows = []
        # Only <pid>.json: the sibling .key files hold private peer tokens.
        for path in (self.home / 'sessions').glob('*.json'):
            if not path.stem.isdigit():
                continue
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                pid = int(data['pid'])
                session = str(data['sessionId'])
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if data.get('kind') not in WATCHED_KINDS or not re.fullmatch(r'[0-9a-fA-F-]{36}', session) or not self.alive(pid, data.get('procStart')):
                continue
            status = str(data.get('status') or 'idle')
            tail = self.transcript(session) if status != 'idle' or session in self.tails else None
            rows.append({'key': session, 'title': str(data.get('name') or Path(str(data.get('cwd') or '')).name or 'Claude 会话'), 'cwd': str(data.get('cwd') or ''),
                         'status': status, 'waitingFor': str(data.get('waitingFor') or ''), 'changed': int(data.get('statusUpdatedAt') or 0),
                         'text': tail.text if tail else '', 'step': tail.step if tail else ''})
        return sorted(rows, key=lambda row: row['changed'], reverse=True)


class ClaudeTaskSync(QObject):
    """Turn session status changes into the pet calls the Codex sync already makes."""

    def __init__(self, pet, reader=None, clock=time.time):
        super().__init__(pet)
        self.pet = pet
        self.reader = reader or ClaudeTaskReader()
        self.clock = clock
        self.known = {}
        self.running = set()
        self.rows = []
        self.bootstrap = True
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.poll)

    def start(self):
        self.timer.start()
        self.poll()

    def stop(self):
        self.timer.stop()

    def details(self):
        if self.pet.hub:
            self.pet.hub.show_panel()

    def status(self):
        rows = [{'title': row['title'], 'state': row['status'], 'detail': row['waitingFor'] and '等待确认' or row['step']} for row in self.rows if row['status'] != 'idle']
        if not self.reader.available():
            return {'state': 'offline', 'sessions': [], 'open': 0}
        state = 'waiting' if any(row['state'] == 'waiting' for row in rows) else ('busy' if rows else 'idle')
        return {'state': state, 'sessions': rows, 'open': len(self.rows)}

    def poll(self):
        try:
            self._poll()
        except (OSError, ValueError, RuntimeError):
            # Qt callbacks must not leak an exception into the paint or event loop.
            pass

    def begin(self, key):
        was_running = bool(self.running)
        self.running.add(key)
        if not was_running:
            self.pet.task_started()

    def end(self, key):
        self.running.discard(key)
        if not self.running:
            self.pet.task_finished()

    def _poll(self):
        if not self.pet.settings.value('syncTasks', True, type=bool):
            return
        self.rows = self.reader.sessions()
        seen = set()
        for row in self.rows:
            key = row['key']
            seen.add(key)
            record = self.known.setdefault(key, {'status': 'idle' if not self.bootstrap else None, 'text': '', 'started': self.clock(), 'title': row['title']})
            record['title'] = row['title']
            previous, status = record['status'], row['status']
            record['status'] = status
            active = status != 'idle'
            if active and key not in self.running:
                self.begin(key)
                record['started'] = self.clock()
                record['text'] = row['text']
                if previous is not None:
                    self.pet.task_progress('主人，我收到啦！', '这就留意 Claude 的这项任务：' + row['title'], self.details)
            if status == 'waiting' and previous != 'waiting':
                self.pet.task_waiting('主人，这一步需要你确认或补充信息，请到 Claude 查看。', self.details)
            elif status == 'busy' and row['text'] and row['text'] != record['text'] and self.clock() - record['started'] >= 3.5:
                record['text'] = row['text']
                self.pet.task_progress('主人，我忙到这一步啦…', row['text'], self.details)
            if status != 'idle':
                record['settling'] = False
            elif key in self.running and not record.get('settling'):
                # The status can flip just before the final reply reaches the transcript.
                record['settling'] = True
            elif key in self.running:
                self.end(key)
                self.pet.task_completed(row['text'] or 'Claude 已报告本轮任务完成。', self.details)
        for key in [key for key in self.running if key not in seen]:
            # The session is gone, so nothing confirms the work finished.
            self.end(key)
            title = self.known.get(key, {}).get('title', '')
            self.pet.task_progress('主人，任务还没有确认完成。', f'Claude 会话「{title}」已经关闭，请回去看看结果。', self.details)
        for key in [key for key in self.known if key not in seen and key not in self.running]:
            self.known.pop(key)
        self.bootstrap = False


def format_tokens(value):
    return f'{value / 10000:.1f} 万' if value >= 10000 else str(value)


def usage_windows(home=None, cancel=None, now=None):
    """Sum token use from local transcripts. It is what this Mac used, not the remaining allowance."""
    root = claude_home(home) / 'projects'
    now = now or datetime.now().astimezone()
    windows = {'最近 5 小时': now - timedelta(hours=5), '今天': now.replace(hour=0, minute=0, second=0, microsecond=0)}
    earliest = min(windows.values()).timestamp()
    totals = {name: [0, 0, 0] for name in windows}
    seen = set()
    for path in root.glob('*/*.jsonl'):
        if cancel and cancel.is_set():
            break
        try:
            if path.stat().st_mtime < earliest:
                continue
            with path.open('rb') as source:
                for line in source:
                    # Only assistant lines carry usage, and the large log lines are skipped unparsed.
                    if b'"output_tokens"' not in line or b'"assistant"' not in line:
                        continue
                    try:
                        record = json.loads(line)
                        message = record['message']
                        stamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                    except (ValueError, KeyError, TypeError):
                        continue
                    identity = message.get('id')
                    if identity in seen or stamp.timestamp() < earliest:
                        continue
                    seen.add(identity)
                    usage = message.get('usage') or {}
                    fresh = int(usage.get('input_tokens') or 0) + int(usage.get('cache_creation_input_tokens') or 0)
                    for name, start in windows.items():
                        if stamp >= start:
                            totals[name][0] += fresh
                            totals[name][1] += int(usage.get('output_tokens') or 0)
                            totals[name][2] += 1
        except OSError:
            continue
    rows = [{'name': name, 'text': f'输入 {format_tokens(value[0])} · 输出 {format_tokens(value[1])} · {value[2]} 次回复'} for name, value in totals.items()]
    rows.append({'name': '说明', 'text': '这是本机记录的用量，不是账户剩余额度。'})
    return rows
