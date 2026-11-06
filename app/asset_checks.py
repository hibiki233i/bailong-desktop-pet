"""Some tests describe the original 35-clip set, which a replacement character may not ship."""
import json
import unittest
from pathlib import Path

MANIFEST=Path(__file__).resolve().parents[1]/'outputs/白龙桌宠素材/素材清单.json'
FULL_SET=len(json.loads(MANIFEST.read_text(encoding='utf-8'))['variants'])>=15
needs_full_set=unittest.skipUnless(FULL_SET,'需要完整的35段素材')
