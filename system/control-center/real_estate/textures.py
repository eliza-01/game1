"""Real Estate texture selection and canonical format validation.

The FBX-folder listing is a convenience, not a restriction: authors can also use
native Explorer to choose a texture elsewhere. Publication uses the original
file extension so Open Cloud receives the correct MIME type.
"""
from pathlib import Path

TEXTURE_EXTENSIONS = frozenset({'.webp', '.jpg', '.jpeg', '.png'})


def available_textures(folder: Path) -> list[dict]:
    return [
        {'name': path.name, 'path': str(path.resolve())}
        for path in sorted(folder.iterdir(), key=lambda path: path.name.casefold())
        if path.is_file() and path.suffix.lower() in TEXTURE_EXTENSIONS
    ]


def resolve_texture(root: Path, value, *, part: str) -> Path:
    text = str(value or '').strip()
    if not text:
        raise ValueError(f'choose a texture for {part} (WebP, PNG, JPG or JPEG)')
    selected = Path(text).expanduser()
    # Existing registered entries are relative to the project root; Explorer
    # selections and FBX-folder suggestions are absolute local paths.
    if not selected.is_absolute():
        selected = root / selected
    selected = selected.resolve()
    if selected.suffix.lower() not in TEXTURE_EXTENSIONS:
        raise ValueError(f'{part} texture must be WebP, PNG, JPG or JPEG')
    if not selected.is_file():
        raise ValueError(f'{part} texture not found: {selected}')
    return selected
