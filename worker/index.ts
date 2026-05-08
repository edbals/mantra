// Mantra IDX proxy Worker
// Transparently forwards every request to https://www.idx.co.id/<same path>.
// Goal: bypass the Cloudflare WAF block that hits the Hetzner VPS by routing
// through a CF Worker, whose egress sits inside Cloudflare's network.
//
// Health check:  GET /__ping            → "ok"
// Everything else → proxy to www.idx.co.id

const UPSTREAM = "https://www.idx.co.id";

export default {
  async fetch(request: Request): Promise<Response> {
    const incoming = new URL(request.url);

    if (incoming.pathname === "/__ping") {
      return new Response("ok", { headers: { "content-type": "text/plain" } });
    }

    const upstream = new URL(UPSTREAM + incoming.pathname + incoming.search);

    // Build the upstream request: copy method/body, set browser-like headers.
    const headers = new Headers();
    headers.set(
      "User-Agent",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    );
    headers.set("Accept", "application/json, text/plain, */*");
    headers.set("Accept-Language", "en-US,en;q=0.9");
    headers.set("Referer", "https://www.idx.co.id/");

    const upstreamReq = new Request(upstream.toString(), {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer(),
      redirect: "follow",
    });

    const upstreamRes = await fetch(upstreamReq);

    // Pass through body + status. Strip CF/CDN-specific headers so the response
    // cleanly looks like idx.co.id JSON to the caller.
    const respHeaders = new Headers();
    upstreamRes.headers.forEach((v, k) => {
      const lower = k.toLowerCase();
      if (
        !lower.startsWith("cf-") &&
        lower !== "set-cookie" &&
        lower !== "report-to" &&
        lower !== "nel"
      ) {
        respHeaders.set(k, v);
      }
    });

    return new Response(upstreamRes.body, {
      status: upstreamRes.status,
      statusText: upstreamRes.statusText,
      headers: respHeaders,
    });
  },
};
