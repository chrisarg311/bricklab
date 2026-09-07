import { NextRequest, NextResponse } from "next/server";

const ML = process.env.FASTAPI_INTERNAL_URL ?? "http://fastapi:8000";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  try {
    const upstream = await fetch(`${ML}/api/jobs/3d/${jobId}`, {
      signal: AbortSignal.timeout(10_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "ML service unavailable" }, { status: 503 });
  }
}
