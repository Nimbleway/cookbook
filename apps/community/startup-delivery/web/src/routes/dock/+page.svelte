<script lang="ts">
  import { onMount } from "svelte";
  import MarketHeat from "$lib/components/MarketHeat.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { formatRelative } from "$lib/pipeline";
  import type { DeliveryPackage } from "$lib/types";

  interface DockStats {
    total: number;
    verdicts: { build: number; pivot: number; pass: number };
    avgScore: number;
    securedValueUsd: number;
    topTlds: { tld: string; count: number }[];
    topThemes: { token: string; count: number }[];
  }

  let deliveries = $state<DeliveryPackage[]>([]);
  let stats = $state<DockStats | null>(null);
  let loading = $state(true);
  let failed = $state(false);

  const CALL_LABEL: Record<string, string> = { build: "Build it", pivot: "Pivot", pass: "Pass" };

  // Percentage width for each slice of the verdict bar.
  function pct(n: number): number {
    const t = stats ? stats.verdicts.build + stats.verdicts.pivot + stats.verdicts.pass : 0;
    return t > 0 ? Math.round((n / t) * 100) : 0;
  }

  // Compare up to 3 deliveries side-by-side (Tower data over the lakehouse).
  let selectedIds = $state<string[]>([]);
  function toggle(id: string) {
    if (!id) return;
    if (selectedIds.includes(id)) selectedIds = selectedIds.filter((x) => x !== id);
    else if (selectedIds.length < 3) selectedIds = [...selectedIds, id];
  }
  const selected = $derived(
    selectedIds
      .map((id) => deliveries.find((d) => d.trackingId === id))
      .filter((d): d is DeliveryPackage => d != null),
  );
  function competitorCount(d: DeliveryPackage): number {
    return d.marketHeat?.competitorCount ?? d.competitors.length;
  }

  onMount(async () => {
    try {
      const [list, agg] = await Promise.all([
        fetch("/api/deliveries?limit=36").then((r) => r.json()),
        fetch("/api/deliveries/stats").then((r) => r.json()),
      ]);
      deliveries = Array.isArray(list.deliveries) ? list.deliveries : [];
      if (agg && typeof agg.total === "number" && agg.total > 0) stats = agg as DockStats;
    } catch {
      failed = true;
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>The Loading Dock — startup.delivery</title></svelte:head>

<div class="dock">
  <header class="dock__bar">
    <a class="dock__brand" href="/">startup<span class="dock__dot">.</span>delivery</a>
    <a class="dock__back" href="/"><Icon name="refresh" size={16} />Ship an idea</a>
  </header>

  <div class="dock__intro">
    <h1 class="dock__title">The Loading Dock</h1>
    <p class="dock__lede">
      Every idea shipped through the pipeline, recorded to the lakehouse. Live recon in, a named,
      domain-checked package out.
    </p>
  </div>

  {#if loading}
    <div class="dock__grid" aria-hidden="true">
      {#each Array(6) as _, i (i)}<div class="dock__skel"></div>{/each}
    </div>
  {:else if deliveries.length === 0}
    <div class="dock__empty">
      <p>{failed ? "The dock is offline right now." : "Nothing shipped yet."}</p>
      <a class="btn btn--primary" href="/">Ship the first one</a>
    </div>
  {:else}
    {#if stats && stats.total >= 3}
      <section class="stats" aria-label="What the lakehouse has learned">
        <div class="stats__head">
          <h2 class="stats__title">What the dock has learned</h2>
          <span class="stats__total">{stats.total} deliveries</span>
        </div>
        <div class="stats__bar" aria-hidden="true">
          <span class="stats__seg stats__seg--build" style="width: {pct(stats.verdicts.build)}%"></span>
          <span class="stats__seg stats__seg--pivot" style="width: {pct(stats.verdicts.pivot)}%"></span>
          <span class="stats__seg stats__seg--pass" style="width: {pct(stats.verdicts.pass)}%"></span>
        </div>
        <div class="stats__figs">
          <span class="stats__fig stats__fig--build">{stats.verdicts.build} build</span>
          <span class="stats__fig stats__fig--pivot">{stats.verdicts.pivot} pivot</span>
          <span class="stats__fig stats__fig--pass">{stats.verdicts.pass} pass</span>
          <span class="stats__dot">·</span>
          <span class="stats__fig"><b>{stats.avgScore}</b> avg score</span>
          <span class="stats__fig"><b>${stats.securedValueUsd}</b>/yr secured</span>
          {#if stats.topTlds.length}<span class="stats__fig"><b>.{stats.topTlds[0].tld}</b> most claimed</span>{/if}
        </div>
        {#if stats.topThemes.length}
          <div class="stats__themes">
            <span class="stats__themes-label">Contested themes</span>
            {#each stats.topThemes as t (t.token)}
              <span class="stats__chip">{t.token}<b>{t.count}</b></span>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    {#if selected.length > 0}
      <section class="pallet" aria-label="Selected deliveries for comparison">
        <span class="pallet__count">{selected.length} of 3 on the pallet</span>
        <div class="pallet__chips">
          {#each selected as s (s.trackingId)}
            <span class="pallet__chip">{s.brand}</span>
          {/each}
        </div>
        <button type="button" class="pallet__clear" onclick={() => (selectedIds = [])}>Clear</button>
      </section>
    {/if}

    {#if selected.length >= 2}
      <section class="compare" aria-label="Comparison">
        <div class="compare__head">
          <h2 class="compare__title">Comparing {selected.length} deliveries</h2>
          <button type="button" class="compare__clear" onclick={() => (selectedIds = [])}>Clear</button>
        </div>
        <div class="compare__scroll">
          <table class="compare__table">
            <thead>
              <tr>
                <th></th>
                {#each selected as s (s.trackingId)}<th>{s.brand}</th>{/each}
              </tr>
            </thead>
            <tbody>
              <tr><th>Domain</th>{#each selected as s (s.trackingId)}<td class="mono">{s.domain}</td>{/each}</tr>
              <tr><th>Verdict</th>{#each selected as s (s.trackingId)}<td>{s.verdict ? CALL_LABEL[s.verdict.call] ?? s.verdict.call : "—"}</td>{/each}</tr>
              <tr><th>Score</th>{#each selected as s (s.trackingId)}<td>{s.verdict ? `${s.verdict.score}/100` : "—"}</td>{/each}</tr>
              <tr><th>Price</th>{#each selected as s (s.trackingId)}<td>{s.priceUsd != null ? `$${s.priceUsd}/yr` : "—"}</td>{/each}</tr>
              <tr><th>Competitors</th>{#each selected as s (s.trackingId)}<td>{competitorCount(s)}</td>{/each}</tr>
              <tr><th>Market</th>{#each selected as s (s.trackingId)}<td>{s.marketHeat ? (s.marketHeat.crowded ? "crowded" : "open") : "—"}</td>{/each}</tr>
            </tbody>
          </table>
        </div>
      </section>
    {/if}

    <ul class="dock__grid">
      {#each deliveries as d (d.trackingId ?? d.domain)}
        <li class="cell">
          <button
            type="button"
            class="cell__pick"
            class:cell__pick--on={d.trackingId && selectedIds.includes(d.trackingId)}
            aria-pressed={d.trackingId ? selectedIds.includes(d.trackingId) : false}
            disabled={Boolean(d.trackingId) && selectedIds.length >= 3 && !selectedIds.includes(d.trackingId ?? "")}
            title={selectedIds.length >= 3 && d.trackingId && !selectedIds.includes(d.trackingId ?? "") ? "Pallet is full" : "Add to comparison"}
            onclick={() => toggle(d.trackingId ?? "")}
          >
            <Icon name="check" size={13} />
          </button>
          <a class="card card--{d.verdict?.call ?? 'build'}" href="/d/{d.trackingId ?? ''}" aria-label={`View delivery: ${d.brand} (${d.domain})`}>
          <div class="card__top">
            {#if d.trackingId}<span class="card__track">{d.trackingId}</span>{/if}
            {#if d.verdict}
              <span class="card__verdict">{CALL_LABEL[d.verdict.call] ?? d.verdict.call} · {d.verdict.score}</span>
            {/if}
          </div>
          <h2 class="card__brand">{d.brand}</h2>
          <p class="card__domain">
            <span class="card__domain-name">{d.domain}</span>
            {#if d.priceUsd != null}<span class="card__price">${d.priceUsd}/yr</span>{/if}
          </p>
          <p class="card__idea">{d.idea}</p>
          <div class="card__foot">
            {#if d.marketHeat}<MarketHeat heat={d.marketHeat} />{/if}
            {#if d.reconAt}
              <span class="card__fresh">{formatRelative(new Date(d.reconAt))}</span>
            {/if}
          </div>
          </a>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .dock {
    position: relative;
    z-index: 1;
    width: min(100% - 2rem, 64rem);
    margin: 0 auto;
    padding-bottom: var(--space-xxl);
  }

  .dock__bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-md);
    padding: var(--space-lg) 0;
  }

  .dock__brand {
    font-size: 1.0625rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text-primary);
    text-decoration: none;
  }

  .dock__dot {
    color: var(--accent-primary);
  }

  .dock__back {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 8px 14px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    background: var(--surface-raised);
    color: var(--text-secondary);
    font-size: 0.9375rem;
    font-weight: 500;
    text-decoration: none;
  }

  .dock__back:hover {
    color: var(--text-primary);
    border-color: var(--border-strong);
  }

  .dock__intro {
    margin: var(--space-lg) 0 var(--space-xl);
  }

  .dock__title {
    margin: 0;
    font-size: clamp(2rem, 5vw, 2.75rem);
    font-weight: 700;
    letter-spacing: -0.03em;
  }

  .dock__lede {
    margin: var(--space-sm) 0 0;
    max-width: 60ch;
    color: var(--text-secondary);
  }

  .dock__grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
    gap: var(--space-md);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .dock__grid > li {
    display: flex;
  }

  .cell {
    position: relative;
  }

  .cell__pick {
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 2;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-full);
    background: var(--surface-base);
    color: var(--text-muted);
    cursor: pointer;
    opacity: 0.7;
    transition:
      background var(--dur-1) var(--ease-out-quart),
      color var(--dur-1) var(--ease-out-quart),
      opacity var(--dur-1) var(--ease-out-quart);
  }

  .cell__pick:hover {
    color: var(--text-primary);
    opacity: 1;
  }

  .cell__pick:disabled {
    cursor: not-allowed;
    opacity: 0.35;
  }

  .cell__pick--on {
    background: var(--accent-primary);
    border-color: var(--accent-primary);
    color: var(--on-accent);
    opacity: 1;
  }

  .stats {
    margin-bottom: var(--space-lg);
    padding: var(--space-lg);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    background: var(--surface-raised);
  }

  .stats__head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-md);
    margin-bottom: var(--space-md);
  }

  .stats__title {
    margin: 0;
    font-size: 1.0625rem;
    font-weight: 600;
  }

  .stats__total {
    color: var(--text-muted);
    font-size: 0.875rem;
    font-variant-numeric: tabular-nums;
  }

  .stats__bar {
    display: flex;
    height: 10px;
    border-radius: var(--radius-full);
    overflow: hidden;
    background: var(--surface-overlay);
  }

  .stats__seg {
    height: 100%;
  }
  .stats__seg--build {
    background: var(--status-success);
  }
  .stats__seg--pivot {
    background: var(--status-pending);
  }
  .stats__seg--pass {
    background: var(--status-error);
  }

  .stats__figs {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-sm) var(--space-md);
    margin-top: var(--space-sm);
    color: var(--text-secondary);
    font-size: 0.875rem;
  }

  .stats__fig b {
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }

  .stats__fig--build {
    color: var(--status-success);
  }
  .stats__fig--pivot {
    color: var(--status-pending);
  }
  .stats__fig--pass {
    color: var(--status-error);
  }

  .stats__dot {
    color: var(--text-muted);
  }

  .stats__themes {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-sm);
    margin-top: var(--space-md);
    padding-top: var(--space-md);
    border-top: 1px solid var(--border-subtle);
  }

  .stats__themes-label {
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .stats__chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    background: var(--surface-overlay);
    font-size: 0.8125rem;
    color: var(--text-secondary);
  }

  .stats__chip b {
    color: var(--accent-secondary);
    font-variant-numeric: tabular-nums;
  }

  .pallet {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-sm) var(--space-md);
    margin-bottom: var(--space-md);
    padding: 12px 14px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    background: var(--surface-raised);
  }

  .pallet__count {
    color: var(--text-secondary);
    font-size: 0.875rem;
    font-weight: 600;
  }

  .pallet__chips {
    display: inline-flex;
    flex-wrap: wrap;
    gap: var(--space-sm);
  }

  .pallet__chip {
    padding: 4px 9px;
    border-radius: var(--radius-full);
    background: var(--surface-overlay);
    color: var(--text-primary);
    font-size: 0.8125rem;
  }

  .pallet__clear {
    margin-left: auto;
    border: none;
    background: none;
    color: var(--accent-secondary);
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
  }

  .compare {
    margin-bottom: var(--space-lg);
    padding: var(--space-lg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-lg);
    background: var(--surface-overlay);
  }

  .compare__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-md);
  }

  .compare__title {
    margin: 0;
    font-size: 1.0625rem;
    font-weight: 600;
  }

  .compare__clear {
    border: none;
    background: none;
    color: var(--accent-secondary);
    font-size: 0.875rem;
    cursor: pointer;
  }

  .compare__scroll {
    overflow-x: auto;
  }

  .compare__table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9375rem;
  }

  .compare__table th,
  .compare__table td {
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-subtle);
    vertical-align: top;
  }

  .compare__table thead th {
    color: var(--text-primary);
    font-weight: 700;
  }

  .compare__table tbody th {
    color: var(--text-muted);
    font-weight: 500;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    white-space: nowrap;
  }

  .compare__table td {
    color: var(--text-secondary);
  }

  .compare__table .mono {
    font-family: var(--font-mono);
    color: var(--text-primary);
  }

  .card {
    --call: var(--status-success);
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    padding: var(--space-lg);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    background: var(--surface-raised);
    color: inherit;
    text-decoration: none;
    transition: border-color var(--dur-1) var(--ease-out-quart), transform var(--dur-1) var(--ease-out-quart);
  }

  .card--pivot {
    --call: var(--status-pending);
  }
  .card--pass {
    --call: var(--status-error);
  }

  .card:hover {
    border-color: var(--border-strong);
    transform: translateY(-2px);
  }

  .card__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-sm);
  }

  .card__track {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--text-muted);
    letter-spacing: 0.03em;
  }

  .card__verdict {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--call);
    white-space: nowrap;
  }

  .card__brand {
    margin: 2px 0 0;
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    overflow-wrap: anywhere;
  }

  .card__domain {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px 10px;
    margin: 0;
  }

  .card__domain-name {
    font-family: var(--font-mono);
    font-size: 0.9375rem;
    color: var(--text-secondary);
  }

  .card__price {
    font-size: 0.8125rem;
    color: var(--status-success);
    font-weight: 600;
  }

  .card__idea {
    margin: 2px 0 var(--space-sm);
    color: var(--text-muted);
    font-size: 0.9375rem;
    line-height: 1.4;
  }

  .card__foot {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-sm);
    margin-top: auto;
  }

  .card__fresh {
    color: var(--text-muted);
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
  }

  .dock__skel {
    height: 13rem;
    border-radius: var(--radius-lg);
    background: linear-gradient(90deg, var(--surface-raised) 0%, var(--surface-overlay) 50%, var(--surface-raised) 100%);
    background-size: 200% 100%;
    animation: dock-shimmer 1.4s linear infinite;
  }

  @keyframes dock-shimmer {
    from { background-position: 200% 0; }
    to { background-position: -200% 0; }
  }

  .dock__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-md);
    padding: var(--space-xxl) 0;
    color: var(--text-secondary);
    text-align: center;
  }

  @media (prefers-reduced-motion: reduce) {
    .dock__skel { animation: none; }
    .card:hover { transform: none; }
  }
</style>
