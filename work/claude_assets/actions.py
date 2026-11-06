"""One looping action per pet state, driven only by code."""
import math

import numpy as np

from motion import FPS, blink_face, smooth


def breath(t, period=2.0):
    return math.sin(2 * math.pi * t / period)


def idle(rig, seconds=4.0):
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        out.append(rig.frame(tilt=1.0 * math.sin(2 * math.pi * t / 4.0), sway=4, phase=2 * math.pi * t / 2.0, stretch=0.009 * breath(t),
                             face=blink_face(t), mascot_lift=1.6 * max(0.0, math.sin(2 * math.pi * t / 2.0 - 0.8))))
    return out


def work(rig, seconds=4.0):
    keys = rig.at(262, 372)
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        tap = 2.0 * math.sin(2 * math.pi * t * 3.0)
        out.append(rig.frame(tilt=1.2 * math.sin(2 * math.pi * t / 2.0), sway=2.5, phase=2 * math.pi * t / 2.0, stretch=0.005 * breath(t),
                             face=blink_face(t, 2.7, 1.4), mascot_lift=2.5 * abs(math.sin(2 * math.pi * t * 1.5)),
                             local=[('shift', keys[0], keys[1], 34, 0.0, tap)]))
    return out


def think(rig, seconds=4.0):
    finger = rig.at(1208, 248)
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        out.append(rig.frame(tilt=3.0 * math.sin(2 * math.pi * t / 4.0), sway=3, phase=2 * math.pi * t / 2.0, stretch=0.008 * breath(t),
                             face=blink_face(t, 2.0, 1.0), mascot_lift=2.0 * max(0.0, math.sin(2 * math.pi * t / 2.0)),
                             local=[('shift', finger[0], finger[1], 26, 0.0, 1.5 * math.sin(2 * math.pi * t * 1.5))]))
    return out


def ask(rig, seconds=3.0):
    hand = rig.at(192, 800)
    elbow = rig.at(212, 846)
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        wave = 13.0 * math.sin(2 * math.pi * t * 1.6)
        out.append(rig.frame(tilt=1.8 * math.sin(2 * math.pi * t / 3.0), sway=3, phase=2 * math.pi * t / 1.5, stretch=0.008 * breath(t, 1.5),
                             face=blink_face(t, 1.5, 0.7), mascot_lift=3.0 * abs(math.sin(2 * math.pi * t * 0.8)),
                             local=[('turn', elbow[0], elbow[1], hand[0], hand[1], 44, wave)]))
    return out


def cheer(rig, seconds=2.0, hops=2):
    fist_a, fist_b = rig.at(640, 200), rig.at(858, 214)
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        u = (t / seconds * hops) % 1.0
        if u < 0.16:
            k = u / 0.16
            lift, stretch = 0.0, -0.07 * math.sin(k * math.pi / 2)
        elif u < 0.74:
            k = (u - 0.16) / 0.58
            lift, stretch = 44 * 4 * k * (1 - k), 0.045 * abs(1 - 2 * k)
        else:
            k = (u - 0.74) / 0.26
            lift, stretch = 0.0, -0.07 * math.exp(-4 * k) * math.cos(k * 7)
        pump = 7.0 * math.sin(2 * math.pi * u)
        out.append(rig.frame(sway=9, phase=2 * math.pi * u, stretch=stretch, lift=lift, tilt=2.5 * math.sin(2 * math.pi * t / seconds),
                             mascot_lift=11 * max(0.0, math.sin(((u - 0.12) % 1.0) * math.pi * 1.6)),
                             local=[('shift', fist_a[0], fist_a[1], 42, 0.0, -pump), ('shift', fist_b[0], fist_b[1], 42, 0.0, -pump)]))
    return out


def sleep(rig, seconds=5.0):
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        b = breath(t, 2.5)
        out.append(rig.frame(tilt=2.2 * b, sway=2, phase=2 * math.pi * t / 2.5, stretch=0.013 * b, mascot_lift=1.0 + b))
    return out


def walk(rig, seconds=2.0, steps=4):
    """Paper-doll walk: rock and hop in place; the app moves the window."""
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        u = t / seconds * steps
        bounce = abs(math.sin(math.pi * u))
        out.append(rig.frame(tilt=4.0 * math.sin(math.pi * u), sway=7, phase=2 * math.pi * u, stretch=0.02 * (bounce - 0.5), lift=10 * bounce,
                             face=blink_face(t, 1.9, 0.8), mascot_lift=6 * abs(math.sin(math.pi * u - 0.6))))
    return out


def pop(rig_from, rig_to, steps=9):
    """State change: dip into a squash, swap the pose, spring back."""
    out = []
    for i in range(steps):
        k = i / (steps - 1)
        dip = math.sin(min(1.0, k * 2) * math.pi / 2)
        if k < 0.5:
            out.append(rig_from.frame(stretch=-0.08 * dip))
        else:
            q = (k - 0.5) * 2
            spring = -0.08 * math.cos(q * math.pi * 1.5) * math.exp(-2.2 * q)
            out.append(rig_to.frame(stretch=spring, mascot_lift=6 * math.sin(q * math.pi)))
    return out


def walk_drawn(rigs, cycles=2, hold=5):
    """Play drawn walk poses, with code adding hair, bounce and mascot motion."""
    out = []
    total = len(rigs) * hold
    for cycle in range(cycles):
        for index, rig in enumerate(rigs):
            for step in range(hold):
                k = (index * hold + step) / total
                bounce = abs(math.sin(2 * math.pi * k))
                out.append(rig.frame(sway=6, phase=2 * math.pi * k, lift=5 * (1 - bounce), mascot_lift=5 * abs(math.sin(2 * math.pi * k - 0.5))))
    return out


def drag(rig, seconds=2.0):
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        out.append(rig.frame(tilt=6.0 * math.sin(2 * math.pi * t / 1.0), sway=12, phase=2 * math.pi * t / 1.0, stretch=0.03 + 0.01 * breath(t, 1.0),
                             mascot_shift=4 * math.sin(2 * math.pi * t / 1.0 - 1.0)))
    return out


def landing(rig, seconds=2.0):
    out = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        out.append(rig.frame(stretch=-0.1 * math.exp(-5 * t) * math.cos(t * 16), sway=6 * math.exp(-2 * t), phase=t * 8,
                             mascot_lift=14 * math.exp(-5 * t) * abs(math.sin(t * 9))))
    return out


ACTIONS = {'stand': ('idle', idle), 'work': ('work', work), 'think': ('think', think), 'ask': ('ask', ask), 'cheer': ('cheer', cheer), 'sleep': ('sleep', sleep)}
