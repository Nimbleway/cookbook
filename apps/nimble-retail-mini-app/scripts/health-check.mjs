#!/usr/bin/env node
// ─── Pre-booth health check ─────────────────────────────────────────────────
// Verifies the LIVE data path end-to-end: for each category, does every
// retailer (Amazon / Walmart / Target) come back with real products via Nimble?
// Hits the same /api/search endpoint the app uses, with refresh:true so it
// always tests genuinely-live Nimble (never the cache).
//
// Usage:
//   node scripts/health-check.mjs                         # checks the deployed URL
//   node scripts/health-check.mjs http://localhost:3000   # checks local
//   node scripts/health-check.mjs <url> "energy drinks" "coffee"   # custom categories
//   npm run health                                          # = deployed URL
//
// Exit code 0 = every retailer responded for every category; 1 = something
// didn't (so it can gate a deploy or run on a cron before the booth opens).

const DEFAULT_URL = "https://nimble-retail-mini-app.vercel.app";
const RETAILERS = ["amazon", "walmart", "target"];

const args = process.argv.slice(2);
const base = (args.find((a) => a.startsWith("http")) || DEFAULT_URL).replace(/\/$/, "");
const cats = args.filter((a) => !a.startsWith("http"));
const categories = cats.length ? cats : ["energy drinks", "coffee", "protein bars"];

const PER_REQUEST_TIMEOUT_MS = 60_000;

async function pull(keyword) {
  const t0 = Date.now();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), PER_REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword, mode: "live", refresh: true }),
      signal: ctrl.signal,
    });
    const source = res.headers.get("x-nimble-source") || "?";
    const text = await res.text(); // NDJSON: one line per retailer + done
    const status = {};
    for (const line of text.split("\n")) {
      if (!line.trim()) continue;
      let evt;
      try {
        evt = JSON.parse(line);
      } catch {
        continue;
      }
      if (evt.type === "retailer") {
        const r = evt.result;
        status[r.retailer] =
          r.status === "ok"
            ? { ok: true, n: r.results.length }
            : { ok: false, err: (r.error || "").slice(0, 60) };
      }
    }
    return { ms: Date.now() - t0, source, status, httpOk: res.ok };
  } finally {
    clearTimeout(timer);
  }
}

const pad = (s, n) => String(s).padEnd(n);
let allHealthy = true;
const failures = [];

console.log(`\nHealth check → ${base}`);
console.log(`(live · cache-bypassed · ${categories.length} categories)\n`);

for (const c of categories) {
  try {
    const { ms, source, status } = await pull(c);
    const cells = RETAILERS.map((r) => {
      const s = status[r];
      if (s?.ok) return `${r}:✓${s.n}`;
      allHealthy = false;
      failures.push(`${c} / ${r}${s?.err ? ` (${s.err})` : ""}`);
      return `${r}:✗`;
    });
    console.log(`  ${pad(c, 16)} ${cells.join("   ")}   ${(ms / 1000).toFixed(1)}s · ${source}`);
  } catch (err) {
    allHealthy = false;
    failures.push(`${c} / request failed: ${err.message}`);
    console.log(`  ${pad(c, 16)} REQUEST FAILED — ${err.message}`);
  }
}

console.log("");
if (allHealthy) {
  console.log("✅ ALL RETAILERS HEALTHY — safe to demo live.\n");
  process.exit(0);
} else {
  console.log("⚠️  NOT ALL RETAILERS RESPONDED:");
  failures.forEach((f) => console.log(`   • ${f}`));
  console.log("   → Re-run; if it persists, demo with FORCE_DEMO=1 (sample shelf) and check Nimble agent status.\n");
  process.exit(1);
}
