export type DetailLevel = "Low" | "Medium" | "High";

export type PaletteColor = {
  name: string;
  hex: string;
  r: number;
  g: number;
  b: number;
};

const rgb = (name: string, r: number, g: number, b: number): PaletteColor => ({
  name,
  r,
  g,
  b,
  hex: `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`,
});

export const PALETTE: PaletteColor[] = [
  rgb("White", 245, 245, 240),
  rgb("Light Gray", 175, 181, 199),
  rgb("Dark Gray", 99, 95, 97),
  rgb("Black", 27, 27, 29),
  rgb("Bright Red", 196, 40, 28),
  rgb("Dark Red", 123, 46, 47),
  rgb("Orange", 218, 133, 65),
  rgb("Bright Yellow", 245, 205, 47),
  rgb("Tan", 215, 197, 153),
  rgb("Reddish Brown", 105, 64, 39),
  rgb("Brown", 88, 57, 39),
  rgb("Lime", 187, 233, 11),
  rgb("Bright Green", 75, 151, 74),
  rgb("Dark Green", 40, 92, 51),
  rgb("Sand Green", 160, 188, 172),
  rgb("Bright Blue", 13, 105, 172),
  rgb("Dark Azure", 7, 139, 201),
  rgb("Sand Blue", 116, 134, 156),
  rgb("Dark Blue", 32, 58, 86),
  rgb("Bright Purple", 205, 98, 152),
  rgb("Medium Lavender", 160, 132, 187),
  rgb("Pink", 253, 195, 217),
];

export const DETAIL_TO_GRID: Record<DetailLevel, number> = {
  Low: 48,
  Medium: 72,
  High: 104,
};

export function gridDimsFor(
  detail: DetailLevel,
  imgW: number,
  imgH: number
): { gridW: number; gridH: number } {
  const long = DETAIL_TO_GRID[detail];
  if (imgW >= imgH) {
    const gridW = long;
    const gridH = Math.max(8, Math.round((imgH / imgW) * long));
    return { gridW, gridH };
  }
  const gridH = long;
  const gridW = Math.max(8, Math.round((imgW / imgH) * long));
  return { gridW, gridH };
}

function nearestPaletteIndex(r: number, g: number, b: number): number {
  let bestIdx = 0;
  let bestDist = Infinity;
  for (let i = 0; i < PALETTE.length; i++) {
    const c = PALETTE[i];
    const dr = c.r - r;
    const dg = c.g - g;
    const db = c.b - b;
    const d = dr * dr + dg * dg + db * db;
    if (d < bestDist) {
      bestDist = d;
      bestIdx = i;
    }
  }
  return bestIdx;
}

export function quantizeImage(
  source: HTMLImageElement | HTMLCanvasElement,
  gridW: number,
  gridH: number
): Uint8Array {
  const off = document.createElement("canvas");
  off.width = gridW;
  off.height = gridH;
  const ctx = off.getContext("2d", { willReadFrequently: true })!;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, 0, 0, gridW, gridH);
  const { data } = ctx.getImageData(0, 0, gridW, gridH);
  const indices = new Uint8Array(gridW * gridH);
  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    indices[p] = nearestPaletteIndex(data[i], data[i + 1], data[i + 2]);
  }
  return indices;
}

export type RenderOptions = {
  brickPx?: number;
  showStuds?: boolean;
  showGrid?: boolean;
};

export function renderMosaic(
  canvas: HTMLCanvasElement,
  indices: Uint8Array | number[],
  gridW: number,
  gridH: number,
  opts: RenderOptions = {}
) {
  const brickPx = opts.brickPx ?? 18;
  const showStuds = opts.showStuds ?? true;
  const showGrid = opts.showGrid ?? true;
  canvas.width = gridW * brickPx;
  canvas.height = gridH * brickPx;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const idx = indices[y * gridW + x];
      const c = PALETTE[idx];
      const px = x * brickPx;
      const py = y * brickPx;
      ctx.fillStyle = c.hex;
      ctx.fillRect(px, py, brickPx, brickPx);

      if (showStuds && brickPx >= 6) {
        const cx = px + brickPx / 2;
        const cy = py + brickPx / 2;
        const r = brickPx * 0.32;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,0.18)`;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(0,0,0,0.25)`;
        ctx.lineWidth = Math.max(1, brickPx * 0.06);
        ctx.stroke();
      }

      if (showGrid && brickPx >= 4) {
        ctx.strokeStyle = "rgba(0,0,0,0.18)";
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, brickPx - 1, brickPx - 1);
      }
    }
  }
}

export function renderMosaicWithHighlight(
  canvas: HTMLCanvasElement,
  indices: Uint8Array | number[],
  gridW: number,
  gridH: number,
  highlightHex: string,
  opts: RenderOptions = {}
) {
  const brickPx = opts.brickPx ?? 18;
  renderMosaic(canvas, indices, gridW, gridH, opts);
  const ctx = canvas.getContext("2d")!;

  ctx.fillStyle = "rgba(0,0,0,0.68)";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const idx = indices[y * gridW + x];
      if (PALETTE[idx].hex !== highlightHex) continue;
      const c = PALETTE[idx];
      const px = x * brickPx;
      const py = y * brickPx;
      ctx.fillStyle = c.hex;
      ctx.fillRect(px, py, brickPx, brickPx);
      if (brickPx >= 6) {
        const cx = px + brickPx / 2;
        const cy = py + brickPx / 2;
        const r = brickPx * 0.32;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.28)";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(0,0,0,0.25)";
        ctx.lineWidth = Math.max(1, brickPx * 0.06);
        ctx.stroke();
      }
    }
  }
}

export function renderBuildStep(
  canvas: HTMLCanvasElement,
  indices: Uint8Array | number[],
  gridW: number,
  gridH: number,
  stepHexes: string[],
  currentStepIdx: number,
  opts: RenderOptions = {}
) {
  const brickPx = opts.brickPx ?? 18;
  canvas.width = gridW * brickPx;
  canvas.height = gridH * brickPx;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const placed = new Set(stepHexes.slice(0, currentStepIdx));
  const currentHex = stepHexes[currentStepIdx] ?? null;

  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const idx = indices[y * gridW + x];
      const c = PALETTE[idx];
      const px = x * brickPx;
      const py = y * brickPx;

      if (c.hex === currentHex) {
        ctx.fillStyle = c.hex;
        ctx.fillRect(px, py, brickPx, brickPx);
        ctx.strokeStyle = "rgba(255,250,180,0.75)";
        ctx.lineWidth = Math.max(1.5, brickPx * 0.09);
        ctx.strokeRect(px + 1, py + 1, brickPx - 2, brickPx - 2);
        if (brickPx >= 6) {
          const cx = px + brickPx / 2;
          const cy = py + brickPx / 2;
          const r = brickPx * 0.32;
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(255,255,255,0.32)";
          ctx.fill();
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(0,0,0,0.25)";
          ctx.lineWidth = Math.max(1, brickPx * 0.06);
          ctx.stroke();
        }
      } else if (placed.has(c.hex)) {
        ctx.globalAlpha = 0.4;
        ctx.fillStyle = c.hex;
        ctx.fillRect(px, py, brickPx, brickPx);
        if (brickPx >= 6) {
          const cx = px + brickPx / 2;
          const cy = py + brickPx / 2;
          ctx.beginPath();
          ctx.arc(cx, cy, brickPx * 0.32, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(255,255,255,0.18)";
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      } else {
        ctx.strokeStyle = "rgba(255,255,255,0.07)";
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, brickPx - 1, brickPx - 1);
      }
    }
  }
}

export type PartsRow = { hex: string; name: string; count: number };

export function buildPartsList(indices: Uint8Array | number[]): PartsRow[] {
  const counts = new Map<number, number>();
  for (let i = 0; i < indices.length; i++) {
    const idx = indices[i];
    counts.set(idx, (counts.get(idx) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([idx, count]) => ({
      hex: PALETTE[idx].hex,
      name: PALETTE[idx].name,
      count,
    }))
    .sort((a, b) => b.count - a.count);
}

export function quantizeImageDithered(
  source: HTMLImageElement | HTMLCanvasElement,
  gridW: number,
  gridH: number
): Uint8Array {
  const off = document.createElement("canvas");
  off.width = gridW;
  off.height = gridH;
  const ctx = off.getContext("2d", { willReadFrequently: true })!;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, 0, 0, gridW, gridH);
  const { data } = ctx.getImageData(0, 0, gridW, gridH);

  const r = new Float32Array(gridW * gridH);
  const g = new Float32Array(gridW * gridH);
  const b = new Float32Array(gridW * gridH);
  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    r[p] = data[i]; g[p] = data[i + 1]; b[p] = data[i + 2];
  }

  const indices = new Uint8Array(gridW * gridH);
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const p = y * gridW + x;
      const rv = Math.max(0, Math.min(255, r[p]));
      const gv = Math.max(0, Math.min(255, g[p]));
      const bv = Math.max(0, Math.min(255, b[p]));
      const idx = nearestPaletteIndex(rv, gv, bv);
      indices[p] = idx;
      const c = PALETTE[idx];
      const er = rv - c.r, eg = gv - c.g, eb = bv - c.b;
      if (x + 1 < gridW) {
        r[p + 1] += er * 7 / 16; g[p + 1] += eg * 7 / 16; b[p + 1] += eb * 7 / 16;
      }
      if (y + 1 < gridH) {
        if (x > 0) {
          r[p + gridW - 1] += er * 3 / 16; g[p + gridW - 1] += eg * 3 / 16; b[p + gridW - 1] += eb * 3 / 16;
        }
        r[p + gridW] += er * 5 / 16; g[p + gridW] += eg * 5 / 16; b[p + gridW] += eb * 5 / 16;
        if (x + 1 < gridW) {
          r[p + gridW + 1] += er / 16; g[p + gridW + 1] += eg / 16; b[p + gridW + 1] += eb / 16;
        }
      }
    }
  }
  return indices;
}

export function loadImageFromDataUrl(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = dataUrl;
  });
}

export function makeSourceThumbDataUrl(
  source: HTMLImageElement | HTMLCanvasElement,
  maxLong = 640
): string {
  const w = "naturalWidth" in source ? source.naturalWidth : source.width;
  const h = "naturalHeight" in source ? source.naturalHeight : source.height;
  const scale = Math.min(1, maxLong / Math.max(w, h));
  const c = document.createElement("canvas");
  c.width = Math.round(w * scale);
  c.height = Math.round(h * scale);
  c.getContext("2d")!.drawImage(source, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.82);
}

export function makeThumbDataUrl(
  indices: Uint8Array | number[],
  gridW: number,
  gridH: number,
  maxLong = 320
): string {
  const brickPx = Math.max(2, Math.floor(maxLong / Math.max(gridW, gridH)));
  const c = document.createElement("canvas");
  renderMosaic(c, indices, gridW, gridH, {
    brickPx,
    showStuds: brickPx >= 8,
    showGrid: false,
  });
  return c.toDataURL("image/jpeg", 0.85);
}
