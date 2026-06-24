<script lang="ts">
  import { onMount, untrack } from "svelte";
  import DeliveryUnbox from "$lib/components/DeliveryUnbox.svelte";
  import OutcomeCapture from "$lib/components/OutcomeCapture.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import type { PageData } from "./$types";
  import type {
    Competitor,
    DeliveryPackage,
    JobPartial,
    JobPhase,
    MarketHeat,
    NameCandidate,
    StepId,
    Verdict,
  } from "$lib/types";
  import {
    activateStep,
    completeThrough,
    initialStepStatuses,
  } from "$lib/pipeline";

  let { data }: { data: PageData } = $props();

  // Use $state.snapshot() to produce a plain (non-reactive) copy of the server
  // data, then seed $state from that. We intentionally own these vars and update
  // them via the client poll — they should NOT re-derive from data on navigation.
  const _snap = untrack(() => $state.snapshot(data));
  let status = $state(_snap.status as "done" | "running" | "error");
  let pkg = $state<DeliveryPackage | null>(_snap.pkg ?? null);
  let partial = $state<JobPartial | null>(_snap.partial ?? null);
  let phase = $state<JobPhase | null>(_snap.phase ?? null);
  let errorMessage = $state<string | null>(_snap.errorMessage ?? null);

  // Safety cap: stop polling after ~6 minutes
  const POLL_CAP_MS = 6 * 60 * 1000;
  let pollCapHit = $state(false);

  // Derive Pipeline props from partial
  let marketSummary = $derived(partial?.marketSummary ?? "");
  let positioningGap = $derived(partial?.positioningGap ?? "");
  let competitors = $derived<Competitor[]>(partial?.competitors ?? []);
  let candidates = $derived<NameCandidate[]>(partial?.candidates ?? []);
  let securedDomain = $derived<string | null>(partial?.securedDomain ?? null);
  let marketHeat = $derived<MarketHeat | null>(partial?.marketHeat ?? null);
  let verdict = $derived<Verdict | null>(partial?.verdict ?? null);
  let learnedFrom = $derived(partial?.learnedFrom ?? 0);
  let trackingId = $derived(data.trackingId);

  let reconAt = $derived.by<Date | null>(() => {
    const s = partial?.reconAt;
    if (!s) return null;
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? null : d;
  });

  let partialPieces = $derived.by(() => {
    const pieces: string[] = [];
    if (competitors.length > 0) pieces.push(`${competitors.length} competitors`);
    if (positioningGap.trim()) pieces.push("gap");
    if (candidates.length > 0) pieces.push(`${candidates.length} names`);
    if (securedDomain) pieces.push("domain pick");
    if (trackingId) pieces.push("tracking ID");
    return pieces;
  });

  function inferFailedStep(snapshot: JobPartial | null): StepId {
    if (snapshot?.securedDomain) return "build";
    if ((snapshot?.candidates ?? []).length > 0) return "check";
    if (snapshot?.positioningGap?.trim()) return "check";
    if ((snapshot?.competitors ?? []).length > 0 || snapshot?.marketSummary?.trim()) return "think";
    return "see";
  }

  // Map phase → Pipeline step statuses
  let stepStatuses = $derived.by(() => {
    const p = phase;
    let s = initialStepStatuses();
    if (!p || p === "start") return activateStep(s, "see");
    if (p === "see") { s = completeThrough(s, "see"); return activateStep(s, "think"); }
    if (p === "think" || p === "verdict" || p === "check") { s = completeThrough(s, "think"); return activateStep(s, "check"); }
    if (p === "secured") return completeThrough(s, "check");
    if (p === "build") { s = completeThrough(s, "check"); return activateStep(s, "build"); }
    if (p === "done") return completeThrough(s, "build");
    if (p === "error") {
      const failed = inferFailedStep(partial);
      if (failed === "think") s = completeThrough(s, "see");
      if (failed === "check") s = completeThrough(s, "think");
      if (failed === "build") s = completeThrough(s, "check");
      return { ...s, [failed]: "error" };
    }
    return s;
  });

  onMount(() => {
    if (status !== "running") return;

    let inFlight = false;
    const startedAt = Date.now();

    const poll = async () => {
      if (inFlight) return;
      if (Date.now() - startedAt > POLL_CAP_MS) {
        pollCapHit = true;
        clearInterval(timer);
        return;
      }
      inFlight = true;
      try {
        const res = await fetch(`/api/jobs/${encodeURIComponent(trackingId)}`, { cache: "no-store" });
        if (!res.ok) { inFlight = false; return; } // transient; keep polling
        const envelope = await res.json();
        phase = envelope.phase ?? phase;
        partial = envelope.partial ?? partial;
        if (envelope.status === "done") {
          pkg = envelope.package;
          status = "done";
          clearInterval(timer);
        } else if (envelope.status === "error") {
          errorMessage = envelope.error ?? null;
          status = "error";
          clearInterval(timer);
        }
      } catch {
        // network hiccup — keep last state, keep polling
      }
      inFlight = false;
    };

    const timer = setInterval(poll, 1200);
    // Kick off immediately
    poll();

    return () => clearInterval(timer);
  });
</script>

<svelte:head>
  {#if status === "done" && pkg}
    <title>{pkg.brand} · delivered by startup.delivery</title>
    <meta name="description" content={pkg.positioningGap} />
    <meta property="og:title" content={`${pkg.brand} (${pkg.domain}) · delivered by startup.delivery`} />
    <meta property="og:description" content={pkg.positioningGap} />
    <meta name="twitter:title" content={`${pkg.brand} · ${pkg.domain}`} />
    <meta name="twitter:description" content={pkg.positioningGap} />
  {:else}
    <title>Delivering "{data.idea}" · startup.delivery</title>
    <meta name="description" content={`Delivering "${data.idea}" · startup.delivery`} />
    <meta property="og:title" content={`Delivering "${data.idea}" · startup.delivery`} />
    <meta property="og:description" content={`Delivering "${data.idea}"`} />
    <meta name="twitter:title" content={`Delivering "${data.idea}" · startup.delivery`} />
    <meta name="twitter:description" content={`Delivering "${data.idea}"`} />
  {/if}
  <!-- Per-delivery generated share card (1200×630) overrides app.html's static /og.png. -->
  <meta property="og:image" content={data.ogImageUrl} />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:image" content={data.ogImageUrl} />
</svelte:head>

<div class="perma">
  <header class="perma__bar">
    <a class="perma__brand" href="/">startup<span class="perma__dot">.</span>delivery</a>
    <div class="perma__actions">
      {#if status === "done" && pkg?.trackingId}
        <a class="perma__json" href="/api/deliveries/{pkg.trackingId}" target="_blank" rel="noopener noreferrer">
          <Icon name="external" size={14} />
          JSON
        </a>
      {/if}
      <a class="perma__cta btn btn--primary btn--sm" href="/">
        <Icon name="spark" size={15} />
        Ship your own idea
      </a>
    </div>
  </header>

  {#if status === "done" && pkg}
    <h1 class="sr-only">Delivered: {pkg.brand}</h1>
    <p class="perma__line">Delivered for <span class="perma__idea">"{pkg.idea}"</span></p>
    <DeliveryUnbox {pkg} />

    <!-- The return path: an owner "update what happened" capture that turns this
         one-shot into a tracked decision. Reflects any prior outcome on the package
         ("you marked: built"); needs a tracking id to key the write. -->
    {#if pkg.trackingId}
      <OutcomeCapture trackingId={pkg.trackingId} variant="permalink" existing={pkg.outcome ?? null} />
    {/if}

  {:else if status === "running"}
    <h1 class="sr-only">Delivering: {data.idea}</h1>
    <p class="perma__line">Delivering <span class="perma__idea">"{data.idea}"</span></p>
    <p class="perma__reassure">
      This page updates live. You can leave and come back anytime.
      Tracking <span class="perma__tid">{trackingId}</span>.
    </p>

    {#if pollCapHit}
      <div class="perma__capmsg" role="status">
        Still working. Refresh to check the latest status.
      </div>
    {/if}

    {#await import("$lib/components/Pipeline.svelte")}
      <div class="lazy-fallback" aria-hidden="true"></div>
    {:then { default: Pipeline }}
      <Pipeline
        statuses={stepStatuses}
        {marketSummary}
        {positioningGap}
        {competitors}
        {candidates}
        {securedDomain}
        {reconAt}
        {marketHeat}
        {trackingId}
        {verdict}
        {learnedFrom}
      />
    {/await}

  {:else}
    <!-- error state -->
    <h1 class="sr-only">Delivery error</h1>
    <p class="perma__line">Delivering <span class="perma__idea">"{data.idea}"</span></p>
    <div class="perma__error" role="alert">
      <p class="perma__error-msg">
        {errorMessage ?? "Something went wrong with this delivery. Refresh to check for a late package, or ship a new idea below."}
      </p>
      {#if partialPieces.length > 0}
        <p class="perma__error-kept">Kept so far: {partialPieces.join(" · ")}</p>
      {/if}
      <p class="perma__error-tid">Tracking ID: <span class="perma__tid">{trackingId}</span></p>
      <a class="btn btn--primary btn--sm perma__error-cta" href="/">
        <Icon name="spark" size={15} />
        Ship a new idea
      </a>
    </div>

    {#if partial}
      <p class="perma__partial-note">The partial package is still here so the work that landed is not lost.</p>
      {#await import("$lib/components/Pipeline.svelte")}
        <div class="lazy-fallback" aria-hidden="true"></div>
      {:then { default: Pipeline }}
        <Pipeline
          statuses={stepStatuses}
          {marketSummary}
          {positioningGap}
          {competitors}
          {candidates}
          {securedDomain}
          {reconAt}
          {marketHeat}
          {trackingId}
          {verdict}
          {learnedFrom}
        />
      {/await}
    {/if}
  {/if}
</div>

<style>
  .perma {
    position: relative;
    z-index: 1;
    width: min(100% - 2rem, 56rem);
    margin: 0 auto;
    padding-bottom: var(--space-xxl);
  }

  .perma__bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-md);
    padding: var(--space-lg) 0;
  }

  .perma__brand {
    font-size: 1.0625rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text-primary);
    text-decoration: none;
  }

  .perma__dot {
    color: var(--accent-primary);
  }

  .perma__actions {
    display: inline-flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .perma__json {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 13px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    text-decoration: none;
  }

  .perma__json:hover {
    border-color: var(--border-strong);
    color: var(--text-primary);
  }

  .perma__cta {
    text-decoration: none;
  }

  .perma__line {
    margin: var(--space-sm) 0 var(--space-lg);
    color: var(--text-muted);
    font-size: 0.9375rem;
  }

  .perma__idea {
    color: var(--text-secondary);
  }

  .perma__reassure {
    margin: 0 0 var(--space-lg);
    color: var(--text-muted);
    font-size: 0.875rem;
    line-height: 1.5;
  }

  .perma__tid {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    color: var(--text-secondary);
  }

  .perma__capmsg {
    margin-bottom: var(--space-lg);
    padding: 12px 16px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    background: var(--surface-raised);
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .perma__error {
    margin-top: var(--space-md);
    padding: 20px 24px;
    border: 1px solid color-mix(in oklch, var(--status-error) 45%, transparent);
    border-radius: var(--radius-md);
    background: color-mix(in oklch, var(--status-error) 8%, transparent);
  }

  .perma__error-msg {
    margin: 0 0 var(--space-sm);
    color: var(--text-primary);
    font-size: 0.9375rem;
    line-height: 1.6;
  }

  .perma__error-kept,
  .perma__error-tid {
    margin: 0 0 var(--space-md);
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .perma__error-kept {
    margin-bottom: var(--space-sm);
  }

  .perma__error-cta {
    text-decoration: none;
  }

  .perma__partial-note {
    margin: var(--space-lg) 0 var(--space-md);
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .lazy-fallback {
    min-height: 40vh;
  }
</style>
