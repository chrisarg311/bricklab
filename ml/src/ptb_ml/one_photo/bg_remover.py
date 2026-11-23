from functools import lru_cache
from pathlib import Path
from rembg import new_session, remove
from PIL import Image


# rembg's default model varies by version and newer ones default to bria-rmbg, which is
# non-commercial (CC BY-NC 4.0); u2net is Apache-2.0. Loaded once, on first use.
@lru_cache(maxsize=1)
def _session():
    return new_session("u2net")


def remove_background(input_img: str | Path, output_img: str | Path) -> Path:
    input_img = Path(input_img)
    output_img = Path(output_img)

    # Check input
    if not input_img.exists():
        raise FileNotFoundError(f"Image not found: {input_img}")

    # Remove background
    with Image.open(input_img) as image:
        image = image.convert("RGBA")
        result = remove(image, session=_session())

    # Save result
    output_img.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_img, "PNG")

    return output_img

if __name__ == "__main__":
    remove_background("test_image.jpg", "test_image_no_bg.png")