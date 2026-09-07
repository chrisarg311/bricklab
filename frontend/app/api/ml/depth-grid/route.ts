import { NextRequest, NextResponse } from "next/server";

const ML_URL = process.env.FASTAPI_INTERNAL_URL ?? "http://fastapi:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const upstream = await fetch(`${ML_URL}/api/depth-grid`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60_000),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "ML service unavailable" }, { status: 503 });
  }
}
