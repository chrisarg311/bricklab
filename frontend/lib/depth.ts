export async function fetchDepthGrid(
  imageDataUrl: string,
  gridW: number,
  gridH: number,
  maxHeight = 8
): Promise<number[] | null> {
  try {
    const res = await fetch("/api/ml/depth-grid", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_b64: imageDataUrl,
        grid_w: gridW,
        grid_h: gridH,
        max_height: maxHeight,
      }),
      signal: AbortSignal.timeout(60_000),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return Array.isArray(data.depths) ? (data.depths as number[]) : null;
  } catch {
    return null;
  }
}
