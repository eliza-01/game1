"""M281: a published v2 animation needs an authored hit timeline, not a whole-model ID."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from timeline_store import TimelineStore  # noqa: E402

CLIP = "human_female__weapon__hands__attack__01"
ANIMATION_ASSET = "82219458610259"
RIG_ASSET = "134874851448365"


class Characters:
    def __init__(self, *, rig_asset=RIG_ASSET, visual_mode="assembly"):
        self.rig_asset = rig_asset
        self.visual_mode = visual_mode

    def list(self):
        return [{
            "id": "human_female", "display_name": "Human Female",
            "visual_mode": self.visual_mode,
            "model_asset_id": None if self.visual_mode == "assembly" else "90313240201",
            "assembly_resolved": {"rig": {"asset_id": self.rig_asset}},
        }]


class Animations:
    def list_for_character(self, character_id):
        return [{"clip_id": CLIP, "slot": "attack", "name": "hands_attack_01",
                 "asset_id": ANIMATION_ASSET, "weapon_set": "hands", "variant": 1}]


class Empty:
    def list(self):
        return []


class TimelineV2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        manifest = self.root / "assets/manifests/attack-timelines.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"schemaVersion": 2, "project": "game1", "timelines": []}), encoding="utf8")

    def store(self, characters=None):
        return TimelineStore(self.root, characters or Characters(), Animations(), Empty(), Empty())

    def test_published_v2_attack_is_not_timeline_ready_until_hit_events_authored(self):
        store = self.store()
        row = store.snapshot()["items"][0]
        self.assertEqual(row["clipId"], CLIP)
        self.assertEqual(row["modelAssetId"], RIG_ASSET)
        self.assertEqual(row["previewMode"], "rig")
        self.assertFalse(row["configured"])
        self.assertEqual(row["events"], {})
        session = store.begin_editor_session(CLIP)
        self.assertEqual(session["modelAssetId"], RIG_ASSET)
        self.assertEqual(session["animationAssetId"], ANIMATION_ASSET)
        self.assertFalse(store.snapshot()["items"][0]["configured"])

        store.save({"clipId": CLIP, "duration": 1.25,
                    "events": {"HitStart": {"normalizedTime": 0.35},
                               "HitEnd": {"normalizedTime": 0.58}}})
        row = store.snapshot()["items"][0]
        self.assertTrue(row["configured"])
        lua = (self.root / "src/shared/combat/AttackTimelineData.luau").read_text("utf8")
        self.assertIn(f'["{CLIP}"]', lua)
        self.assertIn('HitStart = table.freeze({ normalizedTime = 0.35 })', lua)
        self.assertIn('HitEnd = table.freeze({ normalizedTime = 0.58 })', lua)

    def test_missing_rig_does_not_fake_preview(self):
        store = self.store(Characters(rig_asset=""))
        self.assertEqual(store.snapshot()["items"][0]["modelAssetId"], "")
        with self.assertRaisesRegex(ValueError, "publish the selected rig/model"):
            store.begin_editor_session(CLIP)

    def test_legacy_model_preview_stays_supported_without_character_rewrites(self):
        store = self.store(Characters(visual_mode="model"))
        self.assertEqual(store.snapshot()["items"][0]["modelAssetId"], "90313240201")
        self.assertEqual(store.snapshot()["items"][0]["previewMode"], "model")

    def test_incomplete_timeline_does_not_claim_configured(self):
        manifest = self.root / "assets/manifests/attack-timelines.json"
        manifest.write_text(json.dumps({"schemaVersion": 2, "project": "game1", "timelines": [
            {"clipId": CLIP, "duration": 1.2, "events": {"HitStart": {"normalizedTime": 0.4}}}
        ]}), encoding="utf8")
        store = self.store()
        self.assertFalse(store.snapshot()["items"][0]["configured"])


if __name__ == "__main__":
    unittest.main()
