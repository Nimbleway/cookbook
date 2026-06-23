import adapter from "@sveltejs/adapter-vercel";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    // Pin the Vercel runtime explicitly (the local Node version is newer than the
    // adapter auto-detects). nodejs22.x is a current Vercel-supported runtime.
    adapter: adapter({ runtime: "nodejs22.x" }),
    // The agent (agent/landing.py) stages built landing pages into web/public/
    // and returns "/deliveries/<domain>/". Serve that dir as the static root so
    // the in-app landing preview and "Open full page" links resolve.
    files: { assets: "public" },
    // App-level Content-Security-Policy. Configured via kit.csp (NOT a
    // hand-rolled header in hooks) so SvelteKit stays in control of its own
    // inline hydration script/style and injects matching nonces/hashes.
    // mode: "auto" lets Kit auto-add nonces for prerendered pages and hashes
    // for dynamically rendered ones, keeping hydration working.
    csp: {
      mode: "auto",
      directives: {
        // Lock everything to same-origin by default; per-type rules below
        // loosen only where this app genuinely needs it.
        "default-src": ["self"],
        // Bundled JS only. In auto mode Kit injects nonces/hashes for its own
        // inline hydration scripts; no third-party or inline scripts allowed.
        "script-src": ["self"],
        // Svelte ships scoped component styles as inline <style>/style attrs,
        // so 'unsafe-inline' is required here to avoid breaking the UI.
        "style-src": ["self", "unsafe-inline"],
        // Bundled images plus inline data: URIs (icons / small assets).
        "img-src": ["self", "data:"],
        // @fontsource fonts are bundled and served from self; data: covers any
        // inlined font payloads.
        "font-src": ["self", "data:"],
        // Only same-origin fetches (the /api endpoints).
        "connect-src": ["self"],
        // The landing preview iframe loads same-origin /deliveries/<domain>/.
        "frame-src": ["self"],
        // No <object>/<embed>/<applet> plugins anywhere.
        "object-src": ["none"],
        // Pin <base href> to this origin so relative URLs can't be hijacked.
        "base-uri": ["self"],
        // This app may only be framed by itself (clickjacking defense).
        "frame-ancestors": ["self"],
      },
    },
  },
};

export default config;
