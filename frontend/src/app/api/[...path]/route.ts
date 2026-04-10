import { NextRequest, NextResponse } from "next/server";

/** 백엔드 origin (끝의 /api 는 자동 제거) */
function backendOrigin(): string {
  const raw = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  let u = raw.trim().replace(/\/+$/, "");
  if (u.endsWith("/api")) u = u.slice(0, -4);
  return u;
}

/**
 * Next 캐치올 params 가 비는 경우가 있어, pathname 에서 /api/ 이후를 반드시 복구합니다.
 * 이렇게 하지 않으면 백엔드에 `GET /api` 만 가서 FastAPI가 {"detail":"Not Found"} 를 냅니다.
 */
function resolveSegments(req: NextRequest, pathParam: string[] | undefined): string[] {
  if (pathParam?.length) return pathParam;
  const raw = req.nextUrl.pathname.replace(/^\/api\/?/, "").replace(/\/$/, "");
  return raw ? raw.split("/").filter(Boolean) : [];
}

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function proxy(req: NextRequest, pathFromParams: string[] | undefined) {
  const segments = resolveSegments(req, pathFromParams);
  const sub = segments.join("/");
  const origin = backendOrigin();

  if (!sub) {
    return NextResponse.json(
      {
        error:
          "잘못된 API 경로입니다. `/api/health`, `/api/collect` 처럼 하위 경로가 필요합니다.",
        pathname: req.nextUrl.pathname,
      },
      { status: 400 }
    );
  }

  const targetUrl = `${origin}/api/${sub}${req.nextUrl.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (["host", "connection", "content-length", "transfer-encoding"].includes(k)) return;
    headers.set(key, value);
  });

  const init: RequestInit = {
    method: req.method,
    headers,
  };

  if (!["GET", "HEAD", "OPTIONS"].includes(req.method)) {
    const buf = await req.arrayBuffer();
    if (buf.byteLength) init.body = buf;
  }

  const res = await fetch(targetUrl, init);

  const out = new NextResponse(res.body, { status: res.status });
  res.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (["transfer-encoding", "connection"].includes(k)) return;
    out.headers.set(key, value);
  });
  return out;
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
export async function OPTIONS(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
