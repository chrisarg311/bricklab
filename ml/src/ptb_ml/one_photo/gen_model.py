from pathlib import Path
from PIL import Image
import numpy as np
import cv2
import trimesh


def gen_model(input_img: str | Path, output_model: str | Path) -> Path:
    input_img = Path(input_img)
    output_model = Path(output_model)

    # Load image
    img = Image.open(input_img).convert("RGBA")
    img_data = np.array(img)

    # Get house mask
    alpha = img_data[:, :, 3]
    mask = (alpha > 0).astype(np.uint8) * 255

    # Find house outline
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    house_outline = max(contours, key=cv2.contourArea)

    # Simplify outline
    outline_size = cv2.arcLength(house_outline, True)
    simple_outline = cv2.approxPolyDP(house_outline, 0.003 * outline_size, True)
    points = simple_outline.reshape(-1, 2)

    # Find walls
    vertical_lines = []

    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]

        width = abs(int(x2) - int(x1))
        height = abs(int(y2) - int(y1))

        if width < 10 and height > 50:
            vertical_lines.append((x1, y1, x2, y2, height))

    vertical_lines.sort(key=lambda line: line[4], reverse=True)
    walls = vertical_lines[:2]

    # Find house body
    left_wall = min(walls, key=lambda line: min(line[0], line[2]))
    right_wall = max(walls, key=lambda line: max(line[0], line[2]))

    left = int((left_wall[0] + left_wall[2]) / 2)
    right = int((right_wall[0] + right_wall[2]) / 2)
    wall_top = int((min(left_wall[1], left_wall[3]) + min(right_wall[1], right_wall[3])) / 2)
    bottom = int((max(left_wall[1], left_wall[3]) + max(right_wall[1], right_wall[3])) / 2)

    # Find roof
    horizontal_lines = []

    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]

        width = abs(int(x2) - int(x1))
        height = abs(int(y2) - int(y1))

        if height < 10 and width > 50 and y1 < wall_top:
            horizontal_lines.append((x1, y1, x2, y2, width))

    roof_top = min(int((line[1] + line[3]) / 2) for line in horizontal_lines)
    roof_lines = [line for line in horizontal_lines if abs(((line[1] + line[3]) / 2) - roof_top) < 5]

    roof_left = int(min(min(line[0], line[2]) for line in roof_lines))
    roof_right = int(max(max(line[0], line[2]) for line in roof_lines))

    # Find chimney
    chimney_mask = mask[:roof_top - 10, :]
    chimney_contours, _ = cv2.findContours(chimney_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    chimney = max(chimney_contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(chimney)

    chimney_left = x
    chimney_right = x + w
    chimney_top = y

    # Create 3D body
    model_width = 10
    scale = model_width / (right - left)

    body_width = (right - left) * scale
    body_height = (bottom - wall_top) * scale
    body_depth = 6

    body = trimesh.creation.box(extents=[body_width, body_depth, body_height])

    # Create roof
    roof_width = body_width + 0.8
    roof_height = 1.5
    roof_depth = body_depth + 0.5

    vertices = np.array([[-roof_width / 2, -roof_depth / 2, 0], [roof_width / 2, -roof_depth / 2, 0], [-roof_width / 2, roof_depth / 2, 0], [roof_width / 2, roof_depth / 2, 0], [-roof_width / 2, 0, roof_height], [roof_width / 2, 0, roof_height]])
    faces = np.array([[0, 1, 5], [0, 5, 4], [2, 4, 5], [2, 5, 3], [0, 4, 2], [1, 3, 5], [0, 2, 1], [1, 2, 3]])

    roof = trimesh.Trimesh(vertices=vertices, faces=faces)
    roof.apply_translation([0, 0, body_height / 2])

    # Create chimney
    chimney_width = (chimney_right - chimney_left) * scale
    chimney_height = (roof_top - chimney_top) * scale
    chimney_depth = 0.8
    chimney_center_x = (((chimney_left + chimney_right) / 2) - ((left + right) / 2)) * scale

    chimney = trimesh.creation.box(extents=[chimney_width, chimney_depth, chimney_height])
    chimney_z = body_height / 2 + roof_height + chimney_height / 2 - 0.5
    chimney.apply_translation([chimney_center_x, 0, chimney_z])

    # Save model
    model = trimesh.util.concatenate([body, roof, chimney])
    output_model.parent.mkdir(parents=True, exist_ok=True)
    model.export(output_model)

    return output_model