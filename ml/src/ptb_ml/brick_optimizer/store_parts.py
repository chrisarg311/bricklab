"""
Store part numbers and prices for the catalog, so a parts list can be ordered
part by part and priced.

Source: the US Pick a Brick store, read 2026-10-16. Each part has a design ID
(the shape) and one element ID per color (shape + color, the orderable item).
Prices are USD each and change over time; `in_stock` is that day's snapshot.
"""
from __future__ import annotations

PRICES_AS_OF = "2026-10-16"
CURRENCY = "USD"
STORE_SEARCH_URL = "https://www.lego.com/en-us/pick-and-build/pick-a-brick?query={design_id}"

# Kit color name -> the store's color name
STORE_COLOR = {"White": "White", "Black": "Black", "Red": "Bright Red"}

# (kind, short side, long side) -> part. elements: kit color -> (element ID, price, in stock)
PARTS: dict[tuple[str, int, int], dict] = {
    ("brick", 1, 1): {"design_id": "3005", "name": "BRICK 1X1",
                      "elements": {"White": ("300501", 0.07, True), "Black": ("300526", 0.07, True), "Red": ("300521", 0.07, True)}},
    ("brick", 1, 2): {"design_id": "3004", "name": "BRICK 1X2",
                      "elements": {"White": ("300401", 0.10, True), "Black": ("300426", 0.10, True), "Red": ("300421", 0.10, True)}},
    ("brick", 1, 3): {"design_id": "3622", "name": "BRICK 1X3",
                      "elements": {"White": ("362201", 0.14, True), "Black": ("362226", 0.14, True), "Red": ("362221", 0.14, True)}},
    ("brick", 1, 4): {"design_id": "3010", "name": "BRICK 1X4",
                      "elements": {"White": ("301001", 0.15, True), "Black": ("301026", 0.15, True), "Red": ("301021", 0.15, True)}},
    ("brick", 1, 6): {"design_id": "3009", "name": "BRICK 1X6",
                      "elements": {"White": ("300901", 0.24, True), "Black": ("300926", 0.24, True), "Red": ("300921", 0.24, True)}},
    ("brick", 1, 8): {"design_id": "3008", "name": "BRICK 1X8",
                      "elements": {"White": ("300801", 0.26, True), "Black": ("300826", 0.26, True), "Red": ("300821", 0.26, True)}},
    ("brick", 2, 2): {"design_id": "3003", "name": "BRICK 2X2",
                      "elements": {"White": ("300301", 0.13, True), "Black": ("300326", 0.13, True), "Red": ("300321", 0.13, True)}},
    ("brick", 2, 3): {"design_id": "3002", "name": "BRICK 2X3",
                      "elements": {"White": ("300201", 0.17, True), "Black": ("300226", 0.17, True), "Red": ("300221", 0.17, True)}},
    ("brick", 2, 4): {"design_id": "3001", "name": "BRICK 2X4",
                      "elements": {"White": ("300101", 0.21, True), "Black": ("300126", 0.21, True), "Red": ("300121", 0.21, True)}},
    ("brick", 2, 6): {"design_id": "44237", "name": "BRICK 2X6",
                      "elements": {"White": ("4181142", 0.31, True), "Black": ("4181144", 0.31, True), "Red": ("4181138", 0.31, True)}},
    ("brick", 2, 8): {"design_id": "93888", "name": "BRICK 2X8",
                      "elements": {"White": ("6033776", 0.39, True), "Black": ("6037390", 0.39, True), "Red": ("6036408", 0.39, False)}},
    ("plate", 1, 1): {"design_id": "3024", "name": "PLATE 1X1",
                      "elements": {"White": ("302401", 0.06, True), "Black": ("302426", 0.06, True), "Red": ("302421", 0.06, True)}},
    ("plate", 1, 2): {"design_id": "3023", "name": "PLATE 1X2",
                      "elements": {"White": ("302301", 0.08, True), "Black": ("302326", 0.08, True), "Red": ("302321", 0.08, True)}},
    ("plate", 1, 4): {"design_id": "3710", "name": "PLATE 1X4",
                      "elements": {"White": ("371001", 0.11, True), "Black": ("371026", 0.11, True), "Red": ("371021", 0.11, True)}},
    ("plate", 1, 6): {"design_id": "3666", "name": "PLATE 1X6",
                      "elements": {"White": ("366601", 0.16, True), "Black": ("366626", 0.16, True), "Red": ("366621", 0.16, True)}},
    ("plate", 1, 8): {"design_id": "3460", "name": "PLATE 1X8",
                      "elements": {"White": ("346001", 0.18, True), "Black": ("346026", 0.18, True), "Red": ("346021", 0.18, True)}},
    ("plate", 2, 2): {"design_id": "3022", "name": "PLATE 2X2",
                      "elements": {"White": ("302201", 0.09, True), "Black": ("302226", 0.09, True), "Red": ("302221", 0.09, True)}},
    ("plate", 2, 4): {"design_id": "3020", "name": "PLATE 2X4",
                      "elements": {"White": ("302001", 0.14, True), "Black": ("302026", 0.14, True), "Red": ("302021", 0.14, True)}},
    ("plate", 2, 6): {"design_id": "3795", "name": "PLATE 2X6",
                      "elements": {"White": ("379501", 0.19, True), "Black": ("379526", 0.19, True), "Red": ("379521", 0.19, True)}},
    ("plate", 2, 8): {"design_id": "3034", "name": "PLATE 2X8",
                      "elements": {"White": ("303401", 0.28, True), "Black": ("303426", 0.28, True), "Red": ("303421", 0.28, True)}},
    ("roof_tile_45", 2, 2): {"design_id": "3039", "name": "ROOF TILE 2X2/45°",
                             "elements": {"White": ("303901", 0.11, True), "Black": ("303926", 0.11, True), "Red": ("303921", 0.11, True)}},
    ("roof_tile_45", 2, 4): {"design_id": "3037", "name": "ROOF TILE 2X4/45°",
                             "elements": {"White": ("303701", 0.17, True), "Black": ("303726", 0.17, True), "Red": ("303721", 0.17, True)}},
    # Green base plates: the 16x16 is sold in Bright Green, the 32x32 only in Dark Green
    ("base_plate", 16, 16): {"design_id": "91405", "name": "PLATE 16X16",
                             "elements": {"Green": ("4611777", 3.29, True)}},
    ("base_plate", 32, 32): {"design_id": "3811", "name": "BASE PLATE 32X32",
                             "elements": {"Green": ("4219692", 10.35, True)}},
}


def store_line(kind: str, w: int, d: int, color: str) -> dict | None:
    """Store details for one part in one kit color, or None if it isn't sold."""
    a, b = sorted((int(w), int(d)))
    part = PARTS.get((kind, a, b))
    if part is None or color not in part["elements"]:
        return None
    element_id, price, in_stock = part["elements"][color]
    return {
        "design_id": part["design_id"],
        "store_name": part["name"],
        "element_id": element_id,
        "unit_price": price,
        "in_stock": in_stock,
        "url": STORE_SEARCH_URL.format(design_id=part["design_id"]),
    }
