from pathlib import Path
from PIL import Image
import numpy as np
import cv2
import trimesh


def gen_model(
    input_img: str | Path,
    output_model: str | Path,
    depth_ratio: float = 0.6,
    debug_img: str | Path | None = None,
) -> Path:
    input_img = Path(input_img)
    output_model = Path(output_model)

    # Load image
    img = Image.open(input_img).convert("RGBA")
    # The pixel thresholds below were tuned on photos this size; larger ones are shrunk
    img.thumbnail((600, 600))
    img_data = np.array(img)

    # Get house mask
    alpha = img_data[:, :, 3]
    if (alpha < 255).mean() < 0.01:
        raise ValueError(f"No transparent background in {input_img}; run bg_remover first")

    # A pixel is house when at least half visible. The opening cuts thin attachments
    # such as paths and railings, then only the largest piece is kept.
    mask = (alpha > 127).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise ValueError(f"No house found in {input_img}")
    biggest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    mask = np.where(labels == biggest, 255, 0).astype(np.uint8)

    # Find house outline
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    house_outline = max(contours, key=cv2.contourArea)

    # Simplify outline
    outline_size = cv2.arcLength(house_outline, True)
    simple_outline = cv2.approxPolyDP(house_outline, 0.003 * outline_size, True)
    points = simple_outline.reshape(-1, 2)

    # Find walls
    rows = np.where(mask.any(axis=1))[0]
    house_middle = (rows[0] + rows[-1]) / 2
    vertical_lines = []

    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]

        width = abs(int(x2) - int(x1))
        height = abs(int(y2) - int(y1))

        # Sideways drift is relative to length so a slightly tilted photo still has walls;
        # walls reach the lower half of the house, which rules out chimney sides
        if width < 0.1 * height and height > 50 and max(y1, y2) > house_middle:
            vertical_lines.append((x1, y1, x2, y2, height))

    if len(vertical_lines) < 2:
        raise ValueError(f"Could not find both side walls in {input_img}")

    # Find house body; the outermost lines are the walls
    left_wall = min(vertical_lines, key=lambda line: min(line[0], line[2]))
    right_wall = max(vertical_lines, key=lambda line: max(line[0], line[2]))

    left = int((left_wall[0] + left_wall[2]) / 2)
    right = int((right_wall[0] + right_wall[2]) / 2)
    if right <= left:
        raise ValueError(f"Could not find both side walls in {input_img}")
    wall_top = int((min(left_wall[1], left_wall[3]) + min(right_wall[1], right_wall[3])) / 2)
    # Height from the shorter wall: clutter touching a wall only lengthens it, and a small
    # tilt moves the wall ends but not their length
    wall_height = min(abs(int(left_wall[3]) - int(left_wall[1])), abs(int(right_wall[3]) - int(right_wall[1])))
    bottom = wall_top + wall_height

    # Find roof
    horizontal_lines = []

    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]

        width = abs(int(x2) - int(x1))
        height = abs(int(y2) - int(y1))

        if height < 10 and width > 50 and y1 < wall_top:
            horizontal_lines.append((x1, y1, x2, y2, width))

    if horizontal_lines:
        roof_top = min(int((line[1] + line[3]) / 2) for line in horizontal_lines)
    else:
        # No flat ridge (pointed or flat roof): the top is the first row above the walls that
        # spans a tenth of the house width, which skips a narrow chimney above the peak
        row_fill = (mask[:wall_top] > 0).sum(axis=1)
        roof_rows = np.where(row_fill >= 0.1 * (right - left))[0]
        roof_top = int(roof_rows[0]) if len(roof_rows) else wall_top

    # Find chimney; optional, and specks above the roof don't count
    chimney_mask = mask[:max(roof_top - 10, 0), :]
    chimney_contours, _ = cv2.findContours(chimney_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    chimney_contours = [c for c in chimney_contours if cv2.contourArea(c) > 0.001 * mask.size]

    chimney_box = None
    if chimney_contours:
        x, y, w, h = cv2.boundingRect(max(chimney_contours, key=cv2.contourArea))
        chimney_left = x
        chimney_right = x + w
        chimney_top = y
        chimney_box = (chimney_left, chimney_top, chimney_right, roof_top)

    if debug_img is not None:
        dbg = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
        cv2.rectangle(dbg, (left, wall_top), (right, bottom), (0, 200, 0), 2)
        cv2.line(dbg, (left, roof_top), (right, roof_top), (255, 120, 0), 2)
        if chimney_box:
            cv2.rectangle(dbg, chimney_box[:2], chimney_box[2:], (0, 0, 255), 2)
        cv2.imwrite(str(debug_img), dbg)

    # Create 3D body
    model_width = 10
    scale = model_width / (right - left)

    body_width = (right - left) * scale
    body_height = (bottom - wall_top) * scale
    # A front photo shows no depth, so it is a ratio of the width until a side photo gives it
    body_depth = body_width * depth_ratio

    body = trimesh.creation.box(extents=[body_width, body_depth, body_height])
    parts = [body]

    # Create roof; one lower than 5% of the walls is a flat roof
    roof_height = (wall_top - roof_top) * scale
    if roof_height < 0.05 * body_height:
        roof_height = 0
    else:
        roof_width = body_width + 0.8
        roof_depth = body_depth + 0.5

        vertices = np.array([[-roof_width / 2, -roof_depth / 2, 0], [roof_width / 2, -roof_depth / 2, 0], [-roof_width / 2, roof_depth / 2, 0], [roof_width / 2, roof_depth / 2, 0], [-roof_width / 2, 0, roof_height], [roof_width / 2, 0, roof_height]])
        faces = np.array([[0, 1, 5], [0, 5, 4], [2, 4, 5], [2, 5, 3], [0, 4, 2], [1, 3, 5], [0, 2, 1], [1, 2, 3]])

        roof = trimesh.Trimesh(vertices=vertices, faces=faces)
        roof.apply_translation([0, 0, body_height / 2])
        parts.append(roof)

    # Create chimney
    if chimney_box:
        chimney_width = (chimney_right - chimney_left) * scale
        chimney_height = (roof_top - chimney_top) * scale
        chimney_depth = 0.8
        chimney_center_x = (((chimney_left + chimney_right) / 2) - ((left + right) / 2)) * scale

        chimney = trimesh.creation.box(extents=[chimney_width, chimney_depth, chimney_height])
        chimney_z = body_height / 2 + roof_height + chimney_height / 2 - 0.5
        chimney.apply_translation([chimney_center_x, 0, chimney_z])
        parts.append(chimney)

    # Save model
    model = trimesh.util.concatenate(parts)
    # Built with Z up; glTF viewers expect Y up
    model.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    output_model.parent.mkdir(parents=True, exist_ok=True)
    model.export(output_model)

    return output_model