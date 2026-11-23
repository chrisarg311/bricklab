"""one_photo.gen_model: house cut-out -> simple 3D model. The cut-outs are drawn
here, so no photo or background-removal model is needed."""
from pathlib import Path

import cv2
import numpy as np
import pytest
import trimesh
from PIL import Image

from ptb_ml.one_photo.gen_model import gen_model

BODY = [(150, 300), (450, 300), (450, 550), (150, 550)]
HIP_ROOF = [(120, 300), (200, 180), (400, 180), (480, 300)]
CHIMNEY = [(330, 110), (370, 110), (370, 200), (330, 200)]
POINTED_ROOF = [(130, 300), (300, 150), (470, 300)]
FLAT_HOUSE = [(150, 200), (450, 200), (450, 550), (150, 550)]

# name -> (polygons, expected number of parts: body, roof, chimney)
SHAPES = {
    "hip roof + chimney": ([BODY, HIP_ROOF, CHIMNEY], 3),
    "no chimney": ([BODY, HIP_ROOF], 2),
    "pointed roof": ([BODY, POINTED_ROOF], 2),
    "flat roof": ([FLAT_HOUSE], 1),
}


def _cutout(path: Path, polygons, size=600) -> Path:
    img = np.zeros((size, size, 4), np.uint8)
    for poly in polygons:
        cv2.fillPoly(img, [np.array(poly, np.int32)], (200, 80, 60, 255))
    cv2.imwrite(str(path), img)
    return path


def _model(tmp_path: Path, image: Path) -> trimesh.Trimesh:
    out = gen_model(image, tmp_path / "out.glb")
    return trimesh.load(out, force="mesh")


@pytest.mark.parametrize("name", SHAPES)
def test_shape_makes_a_model(name, tmp_path):
    polygons, parts = SHAPES[name]
    mesh = _model(tmp_path, _cutout(tmp_path / "in.png", polygons))
    assert mesh.is_volume
    assert len(mesh.split()) == parts


def test_measurements_and_y_up(tmp_path):
    mesh = _model(tmp_path, _cutout(tmp_path / "in.png", [BODY, HIP_ROOF, CHIMNEY]))
    # width 10; body 250/300*10 + roof 120/300*10 + chimney 70/300*10 - 0.5 overlap
    width, height, depth = mesh.extents
    assert width == pytest.approx(10.8)
    assert height == pytest.approx(8.33 + 4.0 + 1.83, abs=0.05)
    assert depth == pytest.approx(6.5)


def test_photo_size_does_not_change_the_model(tmp_path):
    polygons = [BODY, HIP_ROOF, CHIMNEY]
    base = _model(tmp_path, _cutout(tmp_path / "1x.png", polygons)).extents[1]
    big = [[(x * 4, y * 4) for x, y in poly] for poly in polygons]
    large = _model(tmp_path, _cutout(tmp_path / "4x.png", big, size=2400)).extents[1]
    assert large == pytest.approx(base, rel=0.05)


@pytest.mark.parametrize("degrees", [-3, 3])
def test_slight_tilt_keeps_the_size(degrees, tmp_path):
    path = _cutout(tmp_path / "in.png", [BODY, HIP_ROOF, CHIMNEY])
    base = _model(tmp_path, path).extents[1]
    Image.open(path).rotate(degrees, resample=Image.BICUBIC, expand=True).save(path)
    assert _model(tmp_path, path).extents[1] == pytest.approx(base, rel=0.05)


def test_image_without_cutout_is_rejected(tmp_path):
    path = tmp_path / "photo.png"
    Image.new("RGB", (600, 600), "gray").save(path)
    with pytest.raises(ValueError, match="run bg_remover first"):
        gen_model(path, tmp_path / "out.glb")


def test_missing_wall_is_rejected(tmp_path):
    triangle = [(100, 500), (300, 100), (500, 500)]
    with pytest.raises(ValueError, match="side walls"):
        gen_model(_cutout(tmp_path / "in.png", [triangle]), tmp_path / "out.glb")
