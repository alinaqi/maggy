"""Screenshot comparison against an approved baseline: differing pixel count + diff image.

numpy and Pillow come with the optional `maggy[visual]` extra, so they load on first use."""

from __future__ import annotations

from pathlib import Path


def compare(expected: Path, actual: Path, diff: Path) -> int | None:
    """Pixels that differ (any RGBA channel), or None when the sizes differ. The diff image
    is the actual capture faded, with differing pixels in red."""
    import numpy as np
    from PIL import Image

    want = np.asarray(Image.open(expected).convert("RGBA"))
    got = np.asarray(Image.open(actual).convert("RGBA"))
    if want.shape != got.shape:
        return None
    changed = np.any(want != got, axis=-1)
    faded = (got[..., :3] // 4 + 191).astype(np.uint8)
    faded[changed] = (255, 0, 0)
    diff.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(faded, "RGB").save(diff)
    return int(changed.sum())
