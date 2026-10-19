import { NextRequest } from "next/server";

/**
 * Server-side proxy to the Genesis API.
 *
 * In production the browser only talks to this Next.js server, so the API's URL and
 * API key never reach the client and no CORS setup is needed. Configure it with:
 *   BACKEND_URL      e.g. https://genesis-rag-api.onrender.com
 *   BACKEND_API_KEY  the API_KEY configured on the backend (optional)
 */
export const dynamic = "force-dynamic";

const PREFIX = "/api/proxy";
const SKIP_REQUEST_HEADERS = ["host", "connection", "content-length", "accept-encoding", "x-api-key"];
const SKIP_RESPONSE_HEADERS = ["content-encoding", "content-length", "transfer-encoding", "connection"];

async function proxy(req: NextRequest): Promise<Response> {
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    return Response.json({ detail: "BACKEND_URL is not configured on the frontend service" }, { status: 500 });
  }

  const path = req.nextUrl.pathname.slice(PREFIX.length) || "/";
  const target = backend.replace(/\/$/, "") + path + req.nextUrl.search;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!SKIP_REQUEST_HEADERS.includes(key.toLowerCase())) headers.set(key, value);
  });
  if (process.env.BACKEND_API_KEY) headers.set("x-api-key", process.env.BACKEND_API_KEY);

  // The platform's load balancer appends the real visitor address last in x-forwarded-for
  const forwardedFor = req.headers.get("x-forwarded-for");
  const clientIp = forwardedFor ? forwardedFor.split(",").pop()?.trim() : undefined;
  if (clientIp) headers.set("x-genesis-client-ip", clientIp);

  const init: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers,
    redirect: "manual",
    cache: "no-store",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    init.duplex = "half"; // stream uploads straight through
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch {
    return Response.json(
      { detail: "The Genesis API is not reachable. It may be starting up; try again in a minute." },
      { status: 502 }
    );
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!SKIP_RESPONSE_HEADERS.includes(key.toLowerCase())) responseHeaders.set(key, value);
  });
  responseHeaders.set("cache-control", "no-store");
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE, proxy as PATCH, proxy as OPTIONS };
