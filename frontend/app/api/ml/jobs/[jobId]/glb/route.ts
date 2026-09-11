import { NextRequest, NextResponse } from "next/server";

const ML = process.env.FASTAPI_INTERNAL_URL ?? "http://fastapi:8000";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  try {
    const upstream = await fetch(`${ML}/api/jobs/3d/${jobId}/glb`, {
      signal: AbortSignal.timeout(30_000),
    });
    if (!upstream.ok) {
      return NextResponse.json({ error: "GLB not ready" }, { status: upstream.status });
    }
    const buf = await upstream.arrayBuffer();
    return new NextResponse(buf, {
      headers: {
        "Content-Type": "model/gltf-binary",
        "Content-Disposition": `attachment; filename="model_${jobId.slice(0, 8)}.glb"`,
      },
    });
  } catch {
    return NextResponse.json({ error: "ML service unavailable" }, { status: 503 });
  }
}
