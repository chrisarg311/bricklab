import { NextRequest, NextResponse } from "next/server";

const FASTAPI = process.env.FASTAPI_INTERNAL_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const form = await req.formData();

  let upstream: Response;
  try {
    upstream = await fetch(`${FASTAPI}/api/jobs`, {
      method: "POST",
      body: form,
    });
  } catch (err) {
    return NextResponse.json(
      { error: "ML service unreachable", detail: String(err) },
      { status: 502 }
    );
  }

  const data = await upstream.json().catch(() => null);
  return NextResponse.json(data, { status: upstream.status });
}
