# Localization Validation

**Question:** can location-specific retailer intelligence (ZIP / city / DMA) be supported using the **existing** Nimble SERP agents this app already uses?
**Method:** Nimble docs research + live empirical probing (amazon_serp, walmart_serp, target_serp), including a ZIP-A-vs-ZIP-B retest with the documented `localization` flag.
**Date:** 2026-06-01

---

## 1. Location-related fields returned today

| Retailer (agent) | Location field in output | Notes |
|---|---|---|
| Amazon (`amazon_serp`) | `agent_zip_code`, `store_location` | present on every row |
| Walmart (`walmart_serp`) | `store_location` | present |
| Target (`target_serp`) | `store_location` (store name) | present |

So the agents **do** tell you which location a pull came from. The question is whether we can **set** it.

## 2. Are those fields inputs or just metadata?

**Output metadata — not controllable inputs, in practice.** The returned location **rotates randomly on every call**, even with no location param: baseline `amazon_serp` (no geo) returned 10452, then 33168, 11901, 07801 on consecutive calls. The agent picks a location server-side per request.

## 3 & 4. Can the agents be run for a specific ZIP? What works?

**No.** Across **7 candidate param shapes** plus the **documented `localization: true` + `zip_code`** path, none controlled location.

**Probe (no flag):** `zip_code`, `zip`, `agent_zip_code`, `location`, `geo.zip_code`, and top-level `zip_code` all returned HTTP 200 but the reflected ZIP was random and never the requested 90001 across 4 retests each. The one apparent LA hit (90805) did not reproduce — rotation coincidence. `country/state/city` is the only shape the API validates (state must be 2-letter USPS; city is checked against the country), and it **400s** for a real US city ("Unsupported city Los Angeles for state US") — a non-functional path.

**Retest with the documented flag** (`params:{keyword, zip_code, localization:true}`), ZIP A 10001 vs ZIP B 90001, multiple runs:

| Call | Status | Reflected location |
|---|---|---|
| amazon zipA 10001 | 200 | 98944 |
| amazon zipB 90001 | 200 | 98118 |
| amazon zipA 10001 (retest) | 200 | 33844 |
| amazon zipB 90001 (retest) | 200 | 01902 |
| amazon zipB + country=US | 200 | 28277 |
| walmart zipA 10001 | 200 | 32738 |
| walmart zipB 90001 | 200 | 01832 |
| walmart zipB 90001 (retest) | 200 | 34758 |

**Every reflected ZIP is random and unrelated to the requested ZIP.** The `localization: true` flag did not change this. → results cannot be attributed to a chosen location; the ZIP-A-vs-ZIP-B comparison is impossible because neither call honors the input.

**Docs vs. reality:** Nimble docs state `amazon_serp` / `walmart_search` accept `zip_code` + `store_id` with `localization=true`. Our account's agents **silently ignore** these. Likely explanations: geo control is an **account/pipeline-level configuration** (not per-request params), requires a `store_id` obtained via a separate store lookup, or a different agent build than the one provisioned here. It is **not achievable through the documented run params on the agents we have**.

**Latency:** per call ~5–20s with location params — same envelope as today's live pulls (no extra cost), but irrelevant since location isn't honored.

## 5. Validation test result

ZIP A vs ZIP B for **Protein Bars** could **not** be run meaningfully: neither retailer locked to the requested ZIP, so any difference observed is server-side rotation, not localization. **Inconclusive by design — the input isn't respected.**

## 6. Determination

**C — Requires a new Nimble workflow / account-side configuration.**
Location is real *capability* at Nimble (the docs describe it, and the agents clearly geo-vary), but it is **not controllable through the current agents' request params**. Reaching it would require Nimble-side geo configuration, a `store_id` lookup step, or a different agent — i.e., engineering and a Nimble support conversation, not a code change in this app.

For **this prospect/booth experience specifically, the practical answer is D — not worth building now.**

---

## Recommendation: do NOT pursue localization as a built feature. Keep the teaser; move to polish + deploy.

- **Don't build it.** It's gated on Nimble-side work we can't do from here, and forcing it would mean fabricating local data — which violates the credibility principle that drove Sprint 1. We already validated our way out of the wrong build (Seller), and this is the same call.
- **Keep the existing Localization *teaser*** (shipped in Sprint 2): real National column + locked city columns + "Nimble pulls by ZIP/city/DMA — talk to us." It honestly communicates the capability and is a genuine conversation-starter, with zero fabrication.
- **If a client specifically needs localized data,** that's the moment to engage Nimble eng on `store_id`/account geo — a scoped, real project, not booth-demo scope.

### Stop overbuilding — move to launch readiness
The experience is feature-complete and credible. Next steps, in order:
1. **Polish** — copy/spacing pass, ensure every verdict/difference/Run-My-Brand reads cleanly on partial and single-retailer data, final mobile sweep.
2. **Deployment** — ship to Vercel; set `NEXT_PUBLIC_BOOTH_NUMBER`/event env; smoke-test a real live pull in prod.
3. **User testing** — run live category/brand/keyword searches with a few internal reps as stand-in execs; watch where the aha lands and where they hesitate.
4. **Feedback collection** — capture booth reactions (which verdict/divergence drew "I didn't know that") to prioritize any post-launch work.

**Bottom line:** localization is **C/D — not worth pursuing now.** Stop feature development, keep the honest teaser, and move to polish → deploy → test → feedback.
