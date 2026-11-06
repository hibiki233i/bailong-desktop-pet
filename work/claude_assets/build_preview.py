"""Build preview/index.html, one self-contained page with every clip embedded."""
import base64
import io
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
from PIL import Image

from motion import bleed_edges

ROOT = pathlib.Path(__file__).resolve().parents[1]
SIZE = 340
CLIPS = [('idle', '待机', '呼吸、头发摆动、眨眼'), ('work', '工作中', '打字、点头'), ('think', '思考', '歪头、手指轻敲'),
         ('ask', '请求确认', '挥手'), ('cheer', '任务完成', '跳跃、挥拳'), ('sleep', '打瞌睡', '缓慢呼吸'),
         ('walk', '走路', '4 张手绘帧 + 代码'), ('walk_code', '走路（纯代码）', '只用 1 张图')]


def encode(name):
    with Image.open(ROOT / 'out' / f'{name}.webp') as source:
        frames = []
        for index in range(source.n_frames):
            source.seek(index)
            image = source.convert('RGBA').resize((SIZE, SIZE), Image.Resampling.LANCZOS)
            frames.append(Image.fromarray(np.clip(bleed_edges(np.asarray(image).astype(np.float64)) + 0.5, 0, 255).astype(np.uint8), 'RGBA'))
    buffer = io.BytesIO()
    frames[0].save(buffer, 'WEBP', save_all=True, append_images=frames[1:], duration=42, loop=0, quality=80, method=4, exact=True)
    return 'data:image/webp;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')


PAGE = '''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>桌宠动作预览</title>
<style>
:root{--bg:#f6f4f1;--panel:#fff;--ink:#3b2a22;--soft:#7d6a5f;--line:#e7dfd8;--accent:#c96442;--accent-ink:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#1f1c1a;--panel:#2a2623;--ink:#f2ebe5;--soft:#b3a79e;--line:#3d3733;--accent:#e08a66;--accent-ink:#2a1a12}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}
p.lead{margin:0 0 18px;color:var(--soft)}
.stage{position:relative;height:420px;border-radius:14px;overflow:hidden;border:1px solid var(--line);transition:background .25s}
.stage.dark{background:#1b2030}
.stage.light{background:#e9edf3}
.stage.check{background:repeating-conic-gradient(#d9dbe0 0 25%,#f4f5f7 0 50%) 0 0/28px 28px}
#pet{position:absolute;bottom:0;left:0;width:340px;height:340px;user-select:none;-webkit-user-drag:none}
.bar{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0}
.bar.right{margin-top:8px}
button{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:7px 13px;cursor:pointer}
button:hover{border-color:var(--accent)}
button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.note{color:var(--soft);font-size:13px;margin:10px 0 26px}
h2{font-size:16px;margin:0 0 10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px}
figure img{display:block;width:100%;aspect-ratio:1}
figcaption strong{display:block}
figcaption span{color:var(--soft);font-size:13px}
@media (max-width:560px){.stage{height:340px}#pet{width:260px;height:260px}}
</style>
</head>
<body>
<main>
<h1>桌宠动作预览</h1>
<p class="lead">全部动作只用生成的静态图和代码制作，没有视频素材。</p>
<div id="stage" class="stage dark"><img id="pet" alt="当前播放的桌宠动作"></div>
<div class="bar" id="states" role="group" aria-label="切换桌宠状态"></div>
<div class="bar right" id="themes" role="group" aria-label="切换桌面背景"></div>
<p class="note">选择“走路”时，移动由页面代码完成，到边缘后水平镜像，和桌宠项目的做法相同。</p>
<h2>全部动作</h2>
<div class="grid" id="grid"></div>
</main>
<script>
const CLIPS = __CLIPS__;
const pet = document.getElementById('pet'), stage = document.getElementById('stage');
const states = document.getElementById('states'), themes = document.getElementById('themes');
let current = 'idle', x = 0, dir = 1, last = 0;
const center = () => { x = (stage.clientWidth - pet.clientWidth) / 2; };
const place = () => { pet.style.transform = 'translateX(' + x + 'px) scaleX(' + dir + ')'; };
function press(group, target) { group.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b === target)); }
function show(name, button) {
  current = name;
  pet.src = CLIPS.find(c => c.id === name).src;
  if (!name.startsWith('walk')) { dir = 1; center(); place(); }
  press(states, button);
}
function tick(now) {
  const dt = Math.min(50, now - last); last = now;
  if (current.startsWith('walk')) {
    x += dir * dt * 0.075;
    const limit = stage.clientWidth - pet.clientWidth;
    if (x > limit) { x = limit; dir = -1; }
    if (x < 0) { x = 0; dir = 1; }
    place();
  }
  requestAnimationFrame(tick);
}
CLIPS.forEach((clip, index) => {
  const button = document.createElement('button');
  button.textContent = clip.label;
  button.addEventListener('click', () => show(clip.id, button));
  states.appendChild(button);
  const figure = document.createElement('figure');
  figure.innerHTML = '<img alt=""><figcaption><strong></strong><span></span></figcaption>';
  figure.querySelector('img').src = clip.src;
  figure.querySelector('img').alt = clip.label + '动作';
  figure.querySelector('strong').textContent = clip.label;
  figure.querySelector('span').textContent = clip.detail;
  document.getElementById('grid').appendChild(figure);
  if (index === 0) show(clip.id, button);
});
[['dark', '深色桌面'], ['light', '浅色桌面'], ['check', '透明棋盘格']].forEach(([value, label], index) => {
  const button = document.createElement('button');
  button.textContent = label;
  button.addEventListener('click', () => { stage.className = 'stage ' + value; press(themes, button); });
  themes.appendChild(button);
  if (index === 0) press(themes, button);
});
addEventListener('resize', () => { if (!current.startsWith('walk')) { center(); place(); } });
requestAnimationFrame(t => { last = t; tick(t); });
</script>
</body>
</html>
'''


def main():
    clips = [{'id': name, 'label': label, 'detail': detail, 'src': encode(name)} for name, label, detail in CLIPS]
    target = ROOT / 'preview' / 'index.html'
    target.write_text(PAGE.replace('__CLIPS__', json.dumps(clips, ensure_ascii=False)), encoding='utf-8')
    print(target.name, target.stat().st_size // 1048576, 'MiB')


if __name__ == '__main__':
    main()
