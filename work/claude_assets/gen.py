"""Submit one prompt to the local image bridge and copy the verified PNG.

Follows the bridge rules: check health first, one request at a time, wait up to
650 s, and never retry automatically because a retry may spend quota twice.

Usage: python3 gen.py <scene> [output-name]
"""
import json
import pathlib
import shutil
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from prompts import build

BASE = 'http://127.0.0.1:8787'
ROOT = pathlib.Path(__file__).resolve().parents[2] / 'outputs/Claude素材源'


def main():
    scene = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else scene
    target = ROOT / 'raw' / f'{name}.png'
    if target.exists():
        raise SystemExit(f'refusing to overwrite {target.name}')
    with urllib.request.urlopen(BASE + '/health', timeout=8) as response:
        health = json.load(response)
    if not health.get('backend_ready') or health.get('busy'):
        raise SystemExit(f'bridge not available: {health}')

    prompt = build(scene)
    print(f'submit {name}: {len(prompt)} chars', flush=True)
    start = time.monotonic()
    request = urllib.request.Request(BASE + '/generate', data=json.dumps({'prompt': prompt}).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=650) as response:
            status, body = response.status, json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f'HTTP {error.code}: {error.read()[:400]!r}')

    images = body.get('images') or []
    source = pathlib.Path(images[0]['path']) if images else None
    if status != 200 or body.get('status') != 'completed' or not source or not source.is_file():
        raise SystemExit(f'not generated: {status} {str(body)[:400]}')
    target.parent.mkdir(exist_ok=True)
    shutil.copy2(source, target)
    print(f'ok {target.name} {target.stat().st_size // 1024} KiB in {time.monotonic() - start:.0f}s')


if __name__ == '__main__':
    main()
