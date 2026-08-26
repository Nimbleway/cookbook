/**
 * The research brief sent to the Nimble Web Search Agent.
 *
 * Kept in one place so the browser textarea, the CLI defaults, and a custom
 * `DRUG_LIST_PATH` file all send the same instructions. A bare drug list
 * without these directives produces a noticeably thinner report.
 */

export const RESEARCH_DIRECTIVES = `For each drug, research:
- FDA approvals (biosimilars, generics, ANDAs)
- Court dockets (injunctions, settlements, IPR decisions)
- Pricing (WAC, median acquisition cost, any price cuts)
- Manufacturer responses (line extensions, new formulations, marketing pivots)
- Any upcoming patent events within the next 24 months`;

export const EXAMPLE_DRUG_LIST = `1. Humira (adalimumab) — patent expiry 2023. Monitor biosimilar competition, pricing trends, and any remaining patent barriers.

2. Enbrel (etanercept) — patent expiry 2023. Monitor biosimilar competition and any manufacturer responses.

3. Keytruda (pembrolizumab) — core patent expiry 2028. Monitor any early biosimilars, label expansions, and competitor immunotherapies.`;

/**
 * Wrap a drug list (typed text, JSON, or CSV) in the standing research brief.
 *
 * If the caller already supplied the directives — the browser textarea ships
 * them by default and users edit around them — they are not repeated.
 */
export function buildResearchBrief(drugList: string): string {
  const list = drugList.trim();
  if (list.includes('For each drug, research:')) return list;

  return `Run a patent cliff report for these drugs:

${list}

${RESEARCH_DIRECTIVES}`;
}

/** The prefilled brief shown in the browser and used by the CLI with no drug list file. */
export const DEFAULT_BRIEF = buildResearchBrief(EXAMPLE_DRUG_LIST);
