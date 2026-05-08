# mantra-sync Cloudflare Worker

Transparent proxy that forwards requests to `https://www.idx.co.id`. Lives at:

    https://mantra-sync.edbertalso.workers.dev

## Why this exists

The Indonesian Stock Exchange (`www.idx.co.id`) sits behind Cloudflare. The
WAF blocks requests from datacenter IP ranges with HTTP 403 / "Attention
Required". That includes:

- Hetzner (where the live MyMantra dashboard runs)
- GitHub-hosted Actions runners
- Most other VPS providers we'd realistically use

Cloudflare Worker IPs sit *inside* Cloudflare's network and aren't blocked.
This Worker is a thin pass-through: every incoming path is forwarded to the
same path on `idx.co.id` and the response is returned unchanged.

## How it's wired into the daily refresh

The IDX-API project's `src/Client.ts` has been patched (locally on the VPS,
not in the upstream repo) so its `fetcherUrl()` rewrites
`https://www.idx.co.id` → `https://mantra-sync.edbertalso.workers.dev`
before fetching. Existing cron at `0 12 * * 1-5` then works unchanged.

Patch lives at the top of `fetcherUrl()` in `/root/IDX-API/src/Client.ts` on
the VPS. If you ever `git pull` IDX-API and the patch disappears, re-apply
this two-line change:

```ts
async fetcherUrl(url: string, maxAttempts = 5): Promise<Response> {
  // [Mantra] Route through Cloudflare Worker proxy to bypass idx.co.id WAF.
  url = url.replace("https://www.idx.co.id", "https://mantra-sync.edbertalso.workers.dev")
  ...
```

## Deploy

Requires `wrangler` (Cloudflare CLI) and a logged-in account.

```bash
cd worker
npx wrangler login         # one-time, opens browser
npx wrangler deploy
```

## Health check

    curl https://mantra-sync.edbertalso.workers.dev/__ping
    # → ok

## Free-tier limits

100,000 requests/day — the daily sync hits ~30, so we're at <0.05%.
