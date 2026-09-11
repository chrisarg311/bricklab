import { NextRequest, NextResponse } from "next/server";

const ML = process.env.FASTAPI_INTERNAL_URL ?? "http://fastapi:8000";

export async function POST(req: NextRequest) {
  try {
    const upstream = await fetch(`${ML}/api/jobs/3d`, {
      method: "POST",
      body: await req.arrayBuffer(),
      headers: { "Content-Type": req.headers.get("Content-Type") ?? "" },
      signal: AbortSignal.timeout(60_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "ML service unavailable" }, { status: 503 });
  }
}
