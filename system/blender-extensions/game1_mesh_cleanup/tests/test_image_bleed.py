"""Headless test for alpha-preserving mip-safe RGB dilation."""

import importlib.util
from pathlib import Path
import sys

import numpy as np


extension_root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "game1_mesh_cleanup.image_bleed", extension_root / "image_bleed.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


rgba = np.ones((8, 8, 4), dtype=np.float32)
rgba[:, :, 3] = 0.0
rgba[3:5, 3:5, :3] = (0.2, 0.4, 0.1)
rgba[3:5, 3:5, 3] = 1.0
fixed = module.dilate_transparent_rgb(rgba)
assert np.array_equal(fixed[:, :, 3], rgba[:, :, 3])
assert np.allclose(fixed[:, :, :3], (0.2, 0.4, 0.1))
print("GAME1_IMAGE_BLEED_TEST=PASS")
