<script lang="ts">
  import "../app.css";
  import { dev } from "$app/environment";
  import { injectAnalytics } from "@vercel/analytics/sveltekit";

  injectAnalytics({ mode: dev ? "development" : "production" });

  let { children } = $props();
</script>

<svelte:head>
  <title>startup.delivery · one sentence in, proof out</title>
  <meta
    name="description"
    content="Describe your startup in one sentence. We scout the live market, find the gap, and hand back a name you can actually buy."
  />
  <meta name="theme-color" content="#1a1614" />
</svelte:head>

{@render children()}
