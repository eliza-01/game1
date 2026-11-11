"""Create non-destructive alpha-texture copies with mip-safe RGB padding."""

from dataclasses import dataclass
import math
import os

import bpy
import numpy as np


@dataclass(frozen=True)
class ImageBleedStats:
    images_created: int
    nodes_rewired: int


def dilate_transparent_rgb(rgba, alpha_threshold=0.5):
    """Fill transparent RGB from the nearest opaque pixel without changing alpha."""
    height, width, channels = rgba.shape
    if channels != 4:
        raise ValueError("Expected an RGBA image")

    opaque = rgba[:, :, 3] >= alpha_threshold
    if opaque.all() or not opaque.any():
        return rgba.copy()

    grid_y, grid_x = np.indices((height, width), dtype=np.int32)
    seed_y = np.where(opaque, grid_y, -1).astype(np.int32)
    seed_x = np.where(opaque, grid_x, -1).astype(np.int32)
    best_distance = np.where(opaque, 0, np.iinfo(np.int32).max).astype(np.int32)

    step = 1 << max(0, math.ceil(math.log2(max(width, height))) - 1)
    while step >= 1:
        for offset_y, offset_x in (
            (-step, -step),
            (-step, 0),
            (-step, step),
            (0, -step),
            (0, step),
            (step, -step),
            (step, 0),
            (step, step),
        ):
            candidate_y = np.roll(seed_y, (offset_y, offset_x), axis=(0, 1))
            candidate_x = np.roll(seed_x, (offset_y, offset_x), axis=(0, 1))
            valid = candidate_y >= 0
            if offset_y < 0:
                valid[offset_y:, :] = False
            elif offset_y > 0:
                valid[:offset_y, :] = False
            if offset_x < 0:
                valid[:, offset_x:] = False
            elif offset_x > 0:
                valid[:, :offset_x] = False

            distance = (candidate_y - grid_y) ** 2 + (candidate_x - grid_x) ** 2
            better = valid & (distance < best_distance)
            seed_y[better] = candidate_y[better]
            seed_x[better] = candidate_x[better]
            best_distance[better] = distance[better]
        step //= 2

    result = rgba.copy()
    transparent = ~opaque
    result[transparent, :3] = rgba[seed_y[transparent], seed_x[transparent], :3]
    return result


def _fixed_path(image):
    source_path = bpy.path.abspath(image.filepath)
    if not source_path:
        return ""
    stem, _extension = os.path.splitext(source_path)
    return stem + "_mip_safe.png"


def create_mip_safe_copies(materials):
    """Create one fixed copy per alpha image and rewire supplied materials."""
    image_nodes = []
    for material in materials:
        if material is None or material.node_tree is None:
            continue
        for node in material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image is not None:
                image_nodes.append(node)

    source_images = {
        node.image
        for node in image_nodes
        if not node.image.get("game1_mip_safe", False)
    }
    replacements = {}
    for image in source_images:
        width, height = image.size
        if width <= 0 or height <= 0:
            continue
        pixels = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        rgba = pixels.reshape(height, width, 4)
        alpha = rgba[:, :, 3]
        if float(alpha.min()) >= 0.999 or float(alpha.max()) <= 0.001:
            continue

        fixed_rgba = dilate_transparent_rgb(rgba)
        fixed_name = image.name + "_mip_safe"
        fixed = bpy.data.images.get(fixed_name)
        if fixed is not None and fixed.users == 0:
            bpy.data.images.remove(fixed)
            fixed = None
        if fixed is None:
            fixed = bpy.data.images.new(
                fixed_name,
                width=width,
                height=height,
                alpha=True,
                float_buffer=image.is_float,
            )
        elif tuple(fixed.size) != (width, height):
            continue

        fixed.colorspace_settings.name = image.colorspace_settings.name
        fixed.alpha_mode = "STRAIGHT"
        fixed.pixels.foreach_set(fixed_rgba.reshape(-1))
        fixed.update()
        fixed["game1_mip_safe"] = True
        fixed["game1_mip_safe_source"] = image.name

        output_path = _fixed_path(image)
        if output_path:
            fixed.filepath_raw = output_path
            fixed.file_format = "PNG"
            fixed.save()
        else:
            fixed.pack()
        replacements[image] = fixed

    rewired = 0
    for node in image_nodes:
        replacement = replacements.get(node.image)
        if replacement is not None:
            node.image = replacement
            rewired += 1
    return ImageBleedStats(images_created=len(replacements), nodes_rewired=rewired)
