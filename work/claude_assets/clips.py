"""Every clip of the Claude pet: which pose it uses, how it moves, and where it goes.

Poses are still images, so all motion here is code. Motions are periodic and
divide the clip length, which lets idle clips loop without a jump. Every clip
opens with a small spring so the change of pose reads as a hop, not a cut.
"""
import math

from motion import FPS, blink_face


def sine(t, period, phase=0.0):
    return math.sin(2 * math.pi * t / period + phase)


def bounce(t, period):
    return abs(sine(t, 2 * period))


def spring(t):
    return -0.07 * math.exp(-7 * t) * math.cos(20 * t) if t < 0.7 else 0.0


def render(rig, seconds, tilt=1.2, tilt_period=4.0, sway=3.0, breath=2.0, stretch=0.008, mascot=1.6, blink=True, local=None, lift=None, shift=None, turn=None, enter=True):
    frames = []
    for index in range(round(seconds * FPS)):
        t = index / FPS
        frames.append(rig.frame(tilt=tilt * sine(t, tilt_period) + (turn(t) if turn else 0.0), sway=sway, phase=2 * math.pi * t / breath,
                                stretch=stretch * sine(t, breath) + (spring(t) if enter else 0.0), lift=lift(t) if lift else 0.0, shift=shift(t) if shift else 0.0,
                                face=blink_face(t) if blink else 'open', mascot_lift=mascot * max(0.0, sine(t, breath, -0.8)),
                                local=local(t) if local else ()))
    return frames


def hop(t, period=1.0, height=30.0):
    u = (t / period) % 1.0
    return height * 4 * u * (1 - u) if u < 1 else 0.0


def nudge(rig, point, radius, dx=0.0, dy=0.0):
    x, y = rig.at(*point)
    return ('shift', x, y, radius, dx, dy)


def spin(rig, pivot, point, radius, degrees):
    px, py = rig.at(*pivot)
    x, y = rig.at(*point)
    return ('turn', px, py, x, y, radius, degrees)


def stand(r):
    return render(r, 4, tilt=1.0, enter=False)


def think(r):
    return render(r, 4, tilt=3.0, sway=3, local=lambda t: [nudge(r, (1208, 248), 26, dy=1.5 * sine(t, 0.67))], enter=False)


def book(r):
    return render(r, 6, tilt=1.2, tilt_period=6, sway=2, breath=3, local=lambda t: [nudge(r, (215, 335), 56, dy=1.5 * sine(t, 3))])


def pillow(r):
    return render(r, 6, tilt=2.2, tilt_period=6, sway=2, breath=3, stretch=0.013, mascot=1.0, blink=False)


def game(r):
    return render(r, 6, tilt=1.4, tilt_period=3, sway=2, mascot=3, local=lambda t: [nudge(r, (1243, 325), 48, dx=2.2 * sine(t, 0.5), dy=1.2 * sine(t, 0.25))])


def pat(r):
    return render(r, 6, tilt=1.4, tilt_period=3, sway=3, blink=False, local=lambda t: [nudge(r, (180, 545), 56, dy=4.5 * sine(t, 0.75)), nudge(r, (250, 520), 40, dy=3.0 * sine(t, 0.75, -0.8))])


def wave(r):
    return render(r, 4, tilt=1.8, sway=3, breath=2, local=lambda t: [spin(r, (1170, 715), (1120, 670), 66, 15 * sine(t, 0.67))])


def idea(r):
    return render(r, 4, tilt=1.6, sway=3, mascot=3, lift=lambda t: hop(t, 0.6, 22) if t < 0.6 else 0.0, local=lambda t: [nudge(r, (113, 133), 38, dy=4.0 * sine(t, 1.0)), nudge(r, (127, 190), 26, dy=1.5 * sine(t, 1.0))])


def proud(r):
    return render(r, 4, tilt=2.2, sway=3, stretch=0.016, mascot=2.4, blink=False)


def hug(r):
    return render(r, 4, tilt=2.6, sway=4, blink=False, shift=lambda t: 5 * sine(t, 2), local=lambda t: [nudge(r, (1168, 270), 44, dx=-3.5 * sine(t, 1)), nudge(r, (1392, 270), 44, dx=3.5 * sine(t, 1))])


def tsundere(r):
    return render(r, 4, tilt=1.6, sway=2, stretch=0.012, mascot=1.2, blink=False)


def angry(r):
    burst = lambda t: 1.0 if (t % 2.0) < 0.9 else 0.0
    return render(r, 4, tilt=0.6, sway=5, mascot=4, blink=False, breath=1, shift=lambda t: 3.2 * burst(t) * sine(t, 0.14),
                  local=lambda t: [nudge(r, (685, 860), 36, dy=3.0 * burst(t) * sine(t, 0.28)), nudge(r, (852, 860), 36, dy=3.0 * burst(t) * sine(t, 0.28))])


def yawn(r):
    return render(r, 4, tilt=3.0, sway=2, breath=4, stretch=0.022, mascot=1.0, blink=False)


def cookie(r):
    bite = lambda t: 1.0 if (t % 1.25) < 0.55 else 0.0
    return render(r, 5, tilt=1.4, tilt_period=2.5, sway=2, breath=2.5, local=lambda t: [nudge(r, (742, 745), 48, dy=2.6 * bite(t) * sine(t, 0.18))])


def cheer(r):
    frames = []
    seconds, hops = 4.0, 4
    for index in range(round(seconds * FPS)):
        t = index / FPS
        u = (t / seconds * hops) % 1.0
        if u < 0.16:
            lift, stretch = 0.0, -0.07 * math.sin(u / 0.16 * math.pi / 2)
        elif u < 0.74:
            k = (u - 0.16) / 0.58
            lift, stretch = 44 * 4 * k * (1 - k), 0.045 * abs(1 - 2 * k)
        else:
            k = (u - 0.74) / 0.26
            lift, stretch = 0.0, -0.07 * math.exp(-4 * k) * math.cos(k * 7)
        pump = 7.0 * math.sin(2 * math.pi * u)
        frames.append(r.frame(sway=9, phase=2 * math.pi * u, stretch=stretch, lift=lift, tilt=2.5 * math.sin(2 * math.pi * t / 2.0),
                              mascot_lift=11 * max(0.0, math.sin(((u - 0.12) % 1.0) * math.pi * 1.6)),
                              local=[nudge(r, (640, 200), 42, dy=-pump), nudge(r, (858, 214), 42, dy=-pump)]))
    return frames


def heart(r):
    return render(r, 4, tilt=2.4, sway=3, breath=1, local=lambda t: [nudge(r, (250, 265), 46, dy=2.5 * sine(t, 1))])


def sunflower(r):
    return render(r, 4, tilt=1.6, sway=3, local=lambda t: [spin(r, (755, 320), (755, 262), 56, 7 * sine(t, 2)), nudge(r, (755, 262), 46, dy=2.0 * sine(t, 1))])


def bask(r):
    return render(r, 4, tilt=2.0, sway=4, breath=4, stretch=0.014, blink=False, local=lambda t: [nudge(r, (1130, 305), 52, dy=4.0 * sine(t, 2)), nudge(r, (1422, 300), 52, dy=4.0 * sine(t, 2))])


def box(r):
    return render(r, 4, tilt=1.4, sway=4, mascot=3, lift=lambda t: hop(t, 1.0, 12), local=lambda t: [nudge(r, (245, 795), 50, dy=2.4 * sine(t, 0.5))])


def pinwheel(r):
    return render(r, 4, tilt=1.2, sway=4, local=lambda t: [spin(r, (695, 755), (695, 755), 42, 22 * sine(t, 0.5))])


def shy(r):
    return render(r, 4, tilt=3.2, sway=3, stretch=0.01, shift=lambda t: 3 * sine(t, 4))


def salute(r):
    return render(r, 4, tilt=1.0, sway=3, mascot=2.6, lift=lambda t: hop(t, 0.5, 16) if t < 0.5 else 0.0, local=lambda t: [nudge(r, (183, 150), 34, dy=1.2 * sine(t, 0.5))])


def typing(r):
    return render(r, 6, tilt=1.2, tilt_period=2, sway=2.5, stretch=0.005, mascot=2.5, local=lambda t: [nudge(r, (262, 372), 34, dy=2.0 * sine(t, 0.33))])


def folders(r):
    return render(r, 5, tilt=1.8, tilt_period=2.5, sway=3, breath=2.5, shift=lambda t: 4 * sine(t, 2.5), lift=lambda t: 4 * bounce(t, 0.625), local=lambda t: [nudge(r, (760, 265), 52, dy=1.6 * sine(t, 0.625))])


def docs(r):
    return render(r, 5, tilt=1.4, tilt_period=2.5, sway=2, breath=2.5, local=lambda t: [nudge(r, (1255, 270), 66, dy=1.8 * sine(t, 2.5))])


def glass(r):
    return render(r, 4, tilt=2.0, sway=3, local=lambda t: [nudge(r, (138, 718), 62, dx=7 * sine(t, 2), dy=6 * sine(t, 1))])


def clipboard(r):
    return render(r, 4, tilt=1.4, sway=2, local=lambda t: [nudge(r, (695, 750), 28, dx=2.4 * sine(t, 0.25), dy=1.6 * sine(t, 0.5))])


def ask(r):
    return render(r, 3, tilt=1.8, tilt_period=3, sway=3, breath=1.5, mascot=3, local=lambda t: [spin(r, (212, 846), (192, 800), 44, 13 * sine(t, 0.6))])


def dangle(r):
    return render(r, 4, tilt=5.0, tilt_period=2, sway=12, breath=1, stretch=0.012, mascot=1.0, blink=False, enter=False,
                  local=lambda t: [nudge(r, (1225, 950), 42, dx=4 * sine(t, 2, -1)), nudge(r, (1275, 955), 42, dx=4 * sine(t, 2, -1.3))])


def landing(r):
    frames = []
    for index in range(2 * FPS):
        t = index / FPS
        frames.append(r.frame(stretch=-0.1 * math.exp(-5 * t) * math.cos(t * 16), sway=6 * math.exp(-2 * t), phase=t * 8, mascot_lift=14 * math.exp(-5 * t) * abs(math.sin(t * 9))))
    return frames


def drawn_cycle(rigs, seconds, hold, bob, sway=6, mascot=5):
    """Play drawn poses in turn while code adds bob, hair and mascot motion."""
    frames = []
    cycle = len(rigs) * hold
    for index in range(round(seconds * FPS)):
        k = (index % cycle) / cycle
        rig = rigs[(index // hold) % len(rigs)]
        hopped = abs(math.sin(2 * math.pi * k))
        frames.append(rig.frame(sway=sway, phase=2 * math.pi * k, lift=bob * (1 - hopped), mascot_lift=mascot * abs(math.sin(2 * math.pi * k - 0.5))))
    return frames


def floating(rigs, seconds):
    frames = []
    for index in range(round(seconds * FPS)):
        t = index / FPS
        rig = rigs[(index // 12) % len(rigs)]
        frames.append(rig.frame(tilt=2.0 * sine(t, 2.5), sway=5, phase=2 * math.pi * t / 2.5, lift=8 * sine(t, 2.5), mascot_lift=1.5 * max(0.0, sine(t, 1.25))))
    return frames


# id, pose, motion, slot, name, line
POSES = [
    ('idle', 'stand', stand, 'idle', '默认待机', ''),
    ('idle2', 'think', think, 'idles', '想一想', ''),
    ('idle03', 'book', book, 'idles', '待机动作03 · 看绘本', ''),
    ('idle04', 'pillow', pillow, 'idles', '待机动作04 · 抱枕头', ''),
    ('idle05', 'game', game, 'idles', '待机动作05 · 玩掌机', ''),
    ('idle06', 'pat', pat, 'idles', '待机动作06 · 摸摸小伙伴', ''),
    ('01', 'wave', wave, 'variants', '招手/打招呼', '主人来啦！今天也一起把小事做好吧。'),
    ('04', 'idea', idea, 'variants', '灵感', '叮！主人，我想到一个好办法！'),
    ('05', 'proud', proud, 'variants', '得意', '哼哼，这题被我拿下啦。'),
    ('08', 'hug', hug, 'variants', '抱抱', '给主人一个暖暖的抱抱。'),
    ('09', 'tsundere', tsundere, 'variants', '傲娇', '才、才不是特意在等主人呢。'),
    ('13', 'angry', angry, 'variants', '小生气', '这个 bug 太过分了，我要把它拆开！'),
    ('14', 'yawn', yawn, 'variants', '困倦', '哈啊……让我歇一小会儿。'),
    ('17', 'cookie', cookie, 'variants', '偷吃', '这块饼干……是思考用的燃料！'),
    ('18', 'cheer', cheer, 'variants', '庆祝', '完成啦！今天也闪闪发光！'),
    ('20', 'heart', heart, 'variants', '比心', '今日份喜欢，已经送到主人的桌面啦。'),
    ('21', 'sunflower', sunflower, 'variants', '送花', '这朵向日葵，送给主人。'),
    ('22', 'bask', bask, 'variants', '晒太阳', '今天的太阳，暖洋洋的。'),
    ('24', 'box', box, 'variants', '小太阳收藏', '这些小太阳，都是我的宝贝！'),
    ('25', 'pinwheel', pinwheel, 'variants', '吹风车', '呼——风车转起来啦！'),
    ('26', 'shy', shy, 'variants', '害羞', '主人别一直看着我啦……'),
    ('work01', 'salute', salute, 'work', '收到任务', ''),
    ('work02', 'work', typing, 'work', '处理任务', ''),
    ('work03', 'folders', folders, 'work', '整理归档文件', ''),
    ('work04', 'docs', docs, 'work', '翻阅工作资料', ''),
    ('work05', 'glass', glass, 'work', '放大镜查看细节', ''),
    ('drag', 'dangle', dangle, 'dragAnimation', '拖拽', ''),
    ('landing', 'stand', landing, 'landingAnimation', '落地', ''),
    ('quota', 'clipboard', clipboard, 'quotaAnimation', '查看用量', ''),
    ('ask', 'ask', ask, 'askAnimation', '请你确认', ''),
]
