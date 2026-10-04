"""canonical character animation service facade for game1."""
from __future__ import annotations

from pathlib import Path

from animation_core.common import (
    ANIMATION_EXTENSIONS, BASE_SLOT_CATALOG, BOW_EXTRA_SLOTS, MAX_SCAN_FILES, PROJECT,
    SCHEMA_VERSION, WEAPON_SETS, WEAPON_SLOT_CATALOG, classify_animation,
)
from animation_core.publication import AnimationPublicationMixin
from animation_core.registry import AnimationRegistryMixin
from animation_core.storage import AnimationStorageMixin


class AnimationStore(AnimationStorageMixin, AnimationPublicationMixin, AnimationRegistryMixin):
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.runtime = self.root / ".control-center"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.db = self.runtime / "game1.db"
        self._init()
        self._sync_character_profiles()
        self.export()
