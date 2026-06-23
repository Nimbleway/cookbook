// The home route has no server load — it's a pure client `onMount` shell — so
// the idle view can be prerendered to static HTML and served from the CDN.
// (Do NOT prerender /d/[id] or /dock; those have server loads.)
export const prerender = true;
export const ssr = true;
