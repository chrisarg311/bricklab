from __future__ import annotations
import numpy as np



# Subset of common LEGO colors (name, R, G, B)
LEGO_COLORS: list[tuple[str, int, int, int]] = [
    ("White",           255, 255, 255),
    ("Light Bluish Gray", 160, 165, 169),
    ("Dark Bluish Gray", 99,  95,  98),
    ("Black",           33,  33,  33),
    ("Red",             196, 40,  28),
    ("Dark Red",        114, 14,  15),
    ("Orange",          218, 133, 64),
    ("Yellow",          245, 205, 47),
    ("Lime",            166, 202, 85),
    ("Green",           75,  151, 74),
    ("Dark Green",      25,  89,  57),
    ("Bright Blue",     13,  105, 171),
    ("Dark Blue",       20,  48,  68),
    ("Medium Blue",     71,  117, 175),
    ("Tan",             222, 198, 156),
    ("Dark Tan",        138, 114, 78),
    ("Reddish Brown",   105, 64,  39),
    ("Brown",           88,  57,  39),
]

_COLOR_ARRAY = np.array(
    [(r, g, b) for _, r, g, b in LEGO_COLORS], dtype=np.float32
)


def snap_to_lego_color(
        r: int,
        g: int,
        b: int
) -> tuple[int, int, int]:
    """Return the nearest color from the subset above to given RGB"""
    query= np.array([r, g, b], dtype=np.float32)
    dists= np.linalg.norm(_COLOR_ARRAY - query, axis=1)
    idx= int(np.argmin(dists))
    _, nr, ng, nb = LEGO_COLORS[idx]
    return nr, ng, nb