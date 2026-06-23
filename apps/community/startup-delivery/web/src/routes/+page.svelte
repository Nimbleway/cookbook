<script lang="ts">
  import { onMount } from "svelte";
  import Victory from "$lib/components/Victory.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { downloadBrief } from "$lib/brief";
  import {
    initSound,
    setSoundEnabled,
    unlock as unlockSound,
    playTick,
    playReject,
    playSecured,
    playUnbox,
  } from "$lib/sound";
  import { playDemo, DEMO_IDEA } from "$lib/demo";
  import {
    activateStep,
    completeThrough,
    initialStepStatuses,
    normalizeDomain,
    STEP_ORDER,
  } from "$lib/pipeline";
  import type {
    Competitor,
    DeliveryPackage,
    MarketHeat,
    NameCandidate,
    Verdict,
  } from "$lib/types";

  // The live "deliver" tool was retired after the win (see Victory.svelte). The only
  // run left is the self-contained scripted replay (zero network) — the same known-good
  // delivery the agent shipped on camera — triggered by the "Watch the winning run" CTA.
  let idea = $state("");
  let loading = $state(false);
  // Raw landing HTML from the replay transcript (static, no <script>). Rendered ONLY in
  // a sandbox="" srcdoc iframe inside the unbox preview — never injected into this DOM.
  let landingHtml = $state("");
  // Soft cap mirroring the old server cap, so an oversized canned payload can't bloat the DOM.
  const LANDING_HTML_MAX = 262144; // ~256 KB
  let pkg = $state<DeliveryPackage | null>(null);
  let soundOn = $state(false);

  let stepStatuses = $state(initialStepStatuses());
  let marketSummary = $state("");
  let positioningGap = $state("");
  let competitors = $state<Competitor[]>([]);
  let candidates = $state<NameCandidate[]>([]);
  let securedDomain = $state<string | null>(null);
  let reconAt = $state<Date | null>(null);
  let reconFromCache = $state<boolean | null>(null);
  let marketHeat = $state<MarketHeat | null>(null);
  let trackingId = $state<string | null>(null);
  let verdict = $state<Verdict | null>(null);
  let learnedFrom = $state(0);

  let cancelDemo: (() => void) | null = null;
  // True while the scripted replay is the active run — drives the honest
  // "Replay · scripted demo" chip in Pipeline + DeliveryUnbox.
  let demoMode = $state(false);

  const view = $derived(
    pkg
      ? "done"
      : loading || STEP_ORDER.some((s) => stepStatuses[s] !== "idle")
        ? "running"
        : "idle",
  );

  onMount(() => {
    soundOn = initSound();
    // ?demo=1 plays the scripted run once; ?demo=loop loops it (handy for recording).
    const demo = new URLSearchParams(location.search).get("demo");
    if (demo) runDemo(demo === "loop");
    return () => cancelDemo?.();
  });

  function toggleSound() {
    soundOn = !soundOn;
    setSoundEnabled(soundOn);
  }

  function resetRun() {
    pkg = null;
    stepStatuses = initialStepStatuses();
    marketSummary = "";
    positioningGap = "";
    competitors = [];
    candidates = [];
    securedDomain = null;
    reconAt = null;
    reconFromCache = null;
    marketHeat = null;
    trackingId = null;
    verdict = null;
    learnedFrom = 0;
    landingHtml = "";
    demoMode = false;
  }

  function runDemo(loop = false) {
    cancelDemo?.();
    resetRun();
    demoMode = true; // AFTER resetRun() — resetRun() clears it, so set it last
    idea = DEMO_IDEA;
    loading = true;
    stepStatuses = activateStep(stepStatuses, "see");
    cancelDemo = playDemo(
      (kind, data) => handleEvent(kind, data as Record<string, unknown>),
      {
        loop,
        onStart: () => {
          if (soundOn) unlockSound();
          resetRun();
          demoMode = true;
          idea = DEMO_IDEA;
          loading = true;
          stepStatuses = activateStep(stepStatuses, "see");
        },
        onDone: () => (loading = false),
      },
    );
  }

  // The "Watch the winning run" CTA. We have a user gesture here, so unlock audio
  // (cues only play if sound is enabled) and start the replay.
  function watchRun() {
    if (loading) return;
    unlockSound();
    runDemo(false);
  }

  function runAnother() {
    cancelDemo?.();
    cancelDemo = null;
    loading = false;
    resetRun();
    idea = "";
  }

  function candidateKey(candidate: NameCandidate): string {
    const name = candidate.name?.trim().toLowerCase().replace(/\s+/g, "");
    if (name) return `name:${name}`;
    const domain = normalizeDomain(candidate.domain);
    const label = domain.includes(".") ? domain.split(".")[0] : domain;
    return label ? `label:${label}` : `domain:${domain}`;
  }

  function mergeCandidateData(existing: NameCandidate, incoming: NameCandidate): NameCandidate {
    const merged: NameCandidate = { ...existing };
    const bag = merged as unknown as Record<string, unknown>;
    for (const [key, value] of Object.entries(incoming) as [keyof NameCandidate, unknown][]) {
      const prop = String(key);
      if (value === undefined) continue;
      if (value === null && bag[prop] != null) continue;
      if (key === "variants" && Array.isArray(value) && value.length === 0 && merged.variants?.length) continue;
      bag[prop] = value;
    }
    return merged;
  }

  function mergeCandidate(incoming: NameCandidate) {
    const key = candidateKey(incoming);
    const idx = candidates.findIndex((c) => candidateKey(c) === key);
    if (idx >= 0) {
      candidates[idx] = mergeCandidateData(candidates[idx], incoming);
      candidates = [...candidates];
    } else {
      candidates = [...candidates, incoming];
    }
  }

  // Coerce an untrusted landingHtml field to a safe-to-stash string under the cap.
  // Treated as opaque — only ever handed to the sandboxed iframe srcdoc.
  function acceptLandingHtml(raw: unknown): string {
    if (typeof raw !== "string") return "";
    const trimmed = raw.trim();
    if (!trimmed) return "";
    return trimmed.length > LANDING_HTML_MAX ? trimmed.slice(0, LANDING_HTML_MAX) : trimmed;
  }

  function handleEvent(kind: string, data: Record<string, unknown>) {
    if (kind === "start") {
      if (typeof data.trackingId === "string") trackingId = data.trackingId;
      return;
    }

    if (kind === "see") {
      marketSummary = String(data.marketSummary ?? "");
      competitors = (data.competitors as Competitor[]) ?? [];
      const serverReconAt = typeof data.reconAt === "string" ? new Date(data.reconAt) : null;
      reconAt = serverReconAt && !Number.isNaN(serverReconAt.getTime()) ? serverReconAt : new Date();
      reconFromCache = typeof data.reconFromCache === "boolean" ? data.reconFromCache : null;
      marketHeat = (data.marketHeat as MarketHeat | null) ?? null;
      stepStatuses = completeThrough(stepStatuses, "see");
      stepStatuses = activateStep(stepStatuses, "think");
      return;
    }

    if (kind === "think") {
      positioningGap = String(data.positioningGap ?? "");
      if (typeof data.learnedFrom === "number") learnedFrom = data.learnedFrom;
      const next = (data.candidates as NameCandidate[]) ?? [];
      for (const c of next) mergeCandidate(c);
      stepStatuses = completeThrough(stepStatuses, "think");
      stepStatuses = activateStep(stepStatuses, "check");
      return;
    }

    if (kind === "verdict") {
      const v = data.verdict as Verdict | undefined;
      if (v) verdict = v;
      return;
    }

    if (kind === "check") {
      const c = data.candidate as NameCandidate | undefined;
      if (c) {
        mergeCandidate(c);
        if (c.available === false) playReject();
        else playTick();
      }
      if (stepStatuses.check === "idle") {
        stepStatuses = activateStep(stepStatuses, "check");
      }
      return;
    }

    if (kind === "secured") {
      const c = data.candidate as NameCandidate | undefined;
      if (c) {
        mergeCandidate(c);
        securedDomain = normalizeDomain(c.domain);
        playSecured();
      }
      stepStatuses = completeThrough(stepStatuses, "check");
      return;
    }

    if (kind === "build") {
      stepStatuses = completeThrough(stepStatuses, "check");
      const html = acceptLandingHtml(data.landingHtml);
      if (html) {
        landingHtml = html;
        stepStatuses = completeThrough(stepStatuses, "build");
      } else {
        stepStatuses = activateStep(stepStatuses, "build");
      }
      return;
    }

    if (kind === "package") {
      stepStatuses = completeThrough(stepStatuses, "build");
      const pkgHtml = acceptLandingHtml(data.landingHtml);
      if (pkgHtml) landingHtml = pkgHtml;
      const incoming = data as unknown as DeliveryPackage;
      pkg = {
        ...incoming,
        candidates: candidates.length ? candidates : incoming.candidates,
      };
      playUnbox();
      return;
    }
  }
</script>

<div class="app">
  <header class="bar">
    {#if view === "idle"}
      <span class="bar__brand bar__brand--static">startup<span class="bar__dot">.</span>delivery</span>
    {:else}
      <button type="button" class="bar__brand" onclick={runAnother} aria-label="Back to the win">
        startup<span class="bar__dot">.</span>delivery
      </button>
    {/if}

    <div class="bar__actions">
      <button
        type="button"
        class="bar__icon"
        onclick={toggleSound}
        aria-pressed={soundOn}
        title={soundOn ? "Sound on" : "Sound off"}
      >
        <Icon name={soundOn ? "sound" : "mute"} size={16} />
      </button>
    </div>
  </header>

  <main class="stage">
    {#if view === "idle"}
      <Victory ondeliver={watchRun} />
    {:else}
      <h1 class="sr-only">{pkg ? "The winning run" : "Replaying the winning run"}</h1>
      <p class="runline">
        {pkg ? "Delivered for" : "Delivering"}
        <span class="runline__idea">"{idea}"</span>
      </p>

      {#if pkg}
        {#await import("$lib/components/DeliveryUnbox.svelte")}
          <div class="lazy-fallback" aria-hidden="true"></div>
        {:then { default: DeliveryUnbox }}
          <DeliveryUnbox
            pkg={pkg!}
            {landingHtml}
            ondownload={() => pkg && downloadBrief(pkg, pkg.candidates ?? [])}
            onreset={runAnother}
            demo={demoMode}
          />
        {/await}
      {:else}
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
            {reconFromCache}
            {marketHeat}
            {trackingId}
            {verdict}
            {learnedFrom}
            demo={demoMode}
          />
        {/await}
      {/if}
    {/if}
  </main>
</div>

<style>
  .app {
    position: relative;
    z-index: 1;
    width: min(100% - 2rem, 56rem);
    margin: 0 auto;
    padding-bottom: var(--space-xxl);
  }

  .bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-md);
    padding: var(--space-lg) 0;
  }

  .bar__brand {
    font-size: 1.0625rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text-primary);
    background: none;
    border: none;
    padding: 6px 0;
    cursor: pointer;
    font-family: inherit;
  }

  .bar__brand--static {
    cursor: default;
  }

  @media (pointer: coarse) {
    .bar__brand {
      min-height: 44px;
    }
  }

  .bar__dot {
    color: var(--accent-primary);
  }

  .bar__actions {
    display: inline-flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .bar__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    background: var(--surface-raised);
    color: var(--text-muted);
    cursor: pointer;
    transition:
      color var(--dur-1) var(--ease-out-quart),
      border-color var(--dur-1) var(--ease-out-quart);
  }

  .bar__icon[aria-pressed="true"] {
    color: var(--accent-secondary);
    border-color: var(--border-strong);
  }

  .bar__icon:hover {
    color: var(--text-primary);
    border-color: var(--border-strong);
  }

  .stage {
    margin-top: var(--space-md);
  }

  .runline {
    margin: 0 0 var(--space-lg);
    color: var(--text-muted);
    font-size: 0.9375rem;
    animation: fade var(--dur-3) var(--ease-out-quart);
  }

  .runline__idea {
    color: var(--text-secondary);
  }

  @keyframes fade {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  /* Holds layout while a lazily-imported view chunk loads. */
  .lazy-fallback {
    min-height: 40vh;
  }
</style>
