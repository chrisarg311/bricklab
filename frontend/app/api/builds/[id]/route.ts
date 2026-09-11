import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

const FASTAPI = process.env.FASTAPI_INTERNAL_URL ?? "http://localhost:8000";

async function getAuthHeader(): Promise<string | null> {
  const { getToken } = await auth();
  const token = await getToken();
  return token ? `Bearer ${token}` : null;
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const authHeader = await getAuthHeader();
  if (!authHeader) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));

  let upstream: Response;
  try {
    upstream = await fetch(`${FASTAPI}/api/builds/${id}`, {
      method: "PATCH",
      headers: {
        Authorization: authHeader,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
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

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const authHeader = await getAuthHeader();
  if (!authHeader) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${FASTAPI}/api/builds/${id}`, {
      method: "DELETE",
      headers: { Authorization: authHeader },
    });
  } catch (err) {
    return NextResponse.json(
      { error: "ML service unreachable", detail: String(err) },
      { status: 502 }
    );
  }

  // 204 No Content — return empty response
  if (upstream.status === 204) {
    return new NextResponse(null, { status: 204 });
  }
  const data = await upstream.json().catch(() => null);
  return NextResponse.json(data, { status: upstream.status });
}
