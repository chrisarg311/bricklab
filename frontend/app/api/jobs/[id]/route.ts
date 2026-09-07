import { NextRequest, NextResponse } from "next/server";

const FASTAPI = process.env.FASTAPI_INTERNAL_URL ?? "http://localhost:8000";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  let upstream: Response;
  try {
    upstream = await fetch(`${FASTAPI}/api/jobs/${id}`);
  } catch (err) {
    return NextResponse.json(
      { error: "ML service unreachable", detail: String(err) },
      { status: 502 }
    );
  }

  const data = await upstream.json().catch(() => null);
  return NextResponse.json(data, { status: upstream.status });
}
