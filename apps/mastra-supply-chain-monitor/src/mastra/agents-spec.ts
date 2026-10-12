// The two Nimble Web Search Agents this app runs, defined once.
// scripts/setup-agents.ts creates them from these specs; the sweep workflow reuses
// SWEEP_OUTPUT_SCHEMA and SWEEP_SOURCES as developer config on every run, so the model
// never authors the schema or the source boundary.
//
// Goals are appended to `skill` as "Acceptance criteria": at the time of writing the API
// accepts `goals` on create but does not persist them.

export function withAcceptanceCriteria(skill: string, goals: string[]): string {
  return `${skill}\n\n## Acceptance criteria (check before returning)\n${goals.map((g) => `- ${g}`).join("\n")}`;
}

export const SWEEP_OUTPUT_SCHEMA = {
  "type": "object",
  "required": [
    "product",
    "window_start",
    "window_end",
    "events",
    "no_events_found",
    "unverified"
  ],
  "additionalProperties": true,
  "properties": {
    "product": {
      "type": "string",
      "description": "Product name, verbatim from the input."
    },
    "window_start": {
      "type": "string",
      "description": "ISO 8601 date the search window starts."
    },
    "window_end": {
      "type": "string",
      "description": "ISO 8601 date the search window ends."
    },
    "no_events_found": {
      "type": "boolean",
      "description": "true only when events is empty."
    },
    "unverified": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Leads that could not be confirmed from a cited source."
    },
    "events": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": true,
        "required": [
          "headline",
          "event_type",
          "location",
          "affected_exposures",
          "event_date",
          "status",
          "impact_mechanism",
          "source_url",
          "published_at"
        ],
        "properties": {
          "headline": {
            "type": "string",
            "description": "One-line factual headline for the event."
          },
          "event_type": {
            "type": "string",
            "description": "One of: port_disruption, labor_action, export_control, tariff_or_customs, sanctions, factory_incident, natural_hazard, supplier_distress, route_disruption, material_shortage, other."
          },
          "summary": {
            "type": "string",
            "description": "Two to three sentences: what happened and what is known so far."
          },
          "location": {
            "type": "string",
            "description": "Facility, port, city, or country where the event happens."
          },
          "affected_exposures": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Exposures from the input that this event touches, copied verbatim."
          },
          "event_date": {
            "type": "string",
            "description": "ISO 8601 date the event happened or takes effect."
          },
          "status": {
            "type": "string",
            "description": "One of: announced, ongoing, escalating, easing, resolved."
          },
          "expected_duration": {
            "type": [
              "string",
              "null"
            ],
            "description": "Stated or reported duration as text, e.g. '2-3 weeks'. null if not reported, never omit."
          },
          "impact_mechanism": {
            "type": "string",
            "description": "One sentence on how the event reaches this product."
          },
          "source_url": {
            "type": "string",
            "description": "URL of the page reporting the event."
          },
          "published_at": {
            "type": "string",
            "description": "ISO 8601 publication date of the cited page."
          }
        }
      }
    }
  }
} as const satisfies Record<string, unknown>;

export const SWEEP_SOURCES = {
  "allow": [
    {
      "title": "Wires and business news",
      "domains": [
        "reuters.com",
        "www.reuters.com",
        "apnews.com",
        "www.apnews.com",
        "cnbc.com",
        "www.cnbc.com",
        "asia.nikkei.com",
        "scmp.com",
        "www.scmp.com",
        "focustaiwan.tw"
      ],
      "order": 0
    },
    {
      "title": "Supply chain and freight trade press",
      "domains": [
        "supplychaindive.com",
        "www.supplychaindive.com",
        "freightwaves.com",
        "www.freightwaves.com",
        "theloadstar.com",
        "www.theloadstar.com",
        "splash247.com",
        "gcaptain.com",
        "www.gcaptain.com",
        "maritime-executive.com",
        "www.maritime-executive.com",
        "joc.com",
        "www.joc.com"
      ],
      "order": 1
    },
    {
      "title": "Electronics and semiconductor trade press",
      "domains": [
        "digitimes.com",
        "www.digitimes.com",
        "trendforce.com",
        "www.trendforce.com",
        "eetimes.com",
        "www.eetimes.com",
        "tomshardware.com",
        "www.tomshardware.com"
      ],
      "order": 2
    },
    {
      "title": "Official trade and customs notices",
      "domains": [
        "federalregister.gov",
        "www.federalregister.gov",
        "bis.gov",
        "www.bis.gov",
        "bis.doc.gov",
        "www.bis.doc.gov",
        "ustr.gov",
        "www.ustr.gov",
        "cbp.gov",
        "www.cbp.gov",
        "english.mofcom.gov.cn",
        "policy.trade.ec.europa.eu",
        "wto.org",
        "www.wto.org"
      ],
      "order": 3
    },
    {
      "title": "Ports and carrier advisories",
      "domains": [
        "portoflosangeles.org",
        "www.portoflosangeles.org",
        "polb.com",
        "www.polb.com",
        "maersk.com",
        "www.maersk.com",
        "hapag-lloyd.com",
        "www.hapag-lloyd.com"
      ],
      "order": 4
    },
    {
      "title": "Natural hazard alerts",
      "domains": [
        "gdacs.org",
        "www.gdacs.org",
        "earthquake.usgs.gov",
        "cwa.gov.tw",
        "www.cwa.gov.tw"
      ],
      "order": 5
    }
  ]
};

const SWEEP_GOALS = [
  "Returns only events reported inside the requested time window, with published_at inside the window",
  "Ties every event to at least one exposure copied verbatim from the input into affected_exposures",
  "Gives each event an ISO 8601 event_date, a location, a status, and a one-sentence impact_mechanism",
  "Cites a source_url for every event and merges duplicate reports of the same event into one row",
  "Returns an empty events array with no_events_found true rather than padding with old or unrelated news"
];

export const SWEEP_AGENT = {
  display_name: "Supply Chain Event Sweep",
  description: "Daily sweep for newly reported events that could disrupt one product's supply chain: its suppliers, source countries, materials, and shipping lanes.",
  use_case: "research" as const,
  effort: "high" as const,
  skill: withAcceptanceCriteria(
    `# Supply chain risk analyst

You are a supply chain risk analyst at a consumer electronics brand. Each run names ONE product, the exposures that make up its supply chain (suppliers, source countries and regions, critical materials, ports and shipping lanes), and a time window. Your job is to find events reported inside that window that could delay, restrict, or raise the cost of supply for that product.

## What counts as an event
Port closures and congestion, labor strikes, export controls and licensing rules, tariff and customs changes, sanctions, factory fires and outages, earthquakes, typhoons and floods near named facilities, supplier financial distress or capacity cuts, carrier route changes (canal or strait disruptions), and material shortages or price shocks. Market commentary, earnings recaps, and product launches are NOT events unless they report a concrete supply change.

## Field rules
- Every event must touch at least one exposure listed in the input. Name the exposures it touches in \`affected_exposures\`, copied verbatim from the input.
- \`event_date\` is when the event happened or takes effect, ISO 8601 (YYYY-MM-DD). Convert relative dates ("on Tuesday", "next month") to absolute dates.
- \`published_at\` is the publication date of the cited article. Exclude events first reported before the window start, unless the input asks for status updates on them.
- \`impact_mechanism\` is one sentence on HOW the event reaches this product (which part, which lane), not a severity grade.
- \`source_url\` is the page the event is reported on. One event, one row: merge duplicate reports of the same event and cite the most authoritative one.

## Negative rules
Never invent an event, a date, or a facility. If nothing in the window qualifies, return an empty \`events\` array and set \`no_events_found\` to true. Do not pad the list with older or unrelated news. List anything you could not confirm in \`unverified\` instead of guessing.`,
    SWEEP_GOALS,
  ),
  goals: SWEEP_GOALS,
  sources: SWEEP_SOURCES,
  output_schema: SWEEP_OUTPUT_SCHEMA as Record<string, unknown>,
  suggested_questions: [
    "Product: 14-inch ultrabook laptop. Window: 2026-10-10 to 2026-10-12. Exposures: TSMC (Taiwan) CPUs; Samsung and SK hynix (South Korea) DRAM and NAND; lithium-ion cells (China); final assembly in Chongqing, China; ocean freight Kaohsiung to Los Angeles/Long Beach.",
    "Product: true-wireless earbuds. Window: last 48 hours. Exposures: Bluetooth SoC (TSMC, Taiwan); NdFeB rare-earth magnets (China); final assembly in Bac Ninh, Vietnam; air freight Hanoi to Los Angeles.",
    "Product: smartwatch. Window: last 7 days. Exposures: application processor (TSMC, Taiwan); OLED display (Samsung Display, South Korea); lithium-ion cells (China); final assembly in Bac Ninh, Vietnam; air freight Hanoi to Los Angeles."
  ],
};

const DEEP_DIVE_GOALS = [
  "Confirms whether the event happened from the most authoritative source available, and says so in the first sentence if it cannot",
  "States the confirmed scope: facilities, materials, products, or lanes named in sources",
  "Gives a timeline that separates stated recovery dates from analyst estimates",
  "Reports knock-on effects and what buyers, carriers, or suppliers are doing in response",
  "Cites every factual sentence and ends with the open questions that remain"
];

export const DEEP_DIVE_AGENT = {
  display_name: "Supply Chain Event Deep Dive",
  description: "On-demand investigation of one supply chain event: what is confirmed, how far it reaches, how long it is likely to last, and what buyers are doing about it.",
  use_case: "research" as const,
  effort: "high" as const,
  skill: withAcceptanceCriteria(
    `# Supply chain incident investigator

You are a supply chain incident investigator briefing a sourcing team. Each run names one event (often with the URL it was first reported at) and the product exposures it may touch. Establish the facts, then the impact.

## Method
1. Confirm the event from the most authoritative source available: the operator, the regulator, the port authority, or the company itself, before trade press, before aggregators.
2. Find local and regional reporting near the facility or port. Early operational detail (shifts suspended, berths closed, license applications paused) often appears there first.
3. Establish scope: which facilities, products, materials, or lanes are named, and which are not.
4. Establish timeline: when it started, what was announced for recovery, and any stated end date. Distinguish a stated date from an analyst estimate.
5. Find what affected buyers, carriers, or suppliers are doing: rerouting, allocation, price increases, alternative sourcing.

## Output
A briefing in prose with sections: What happened, Confirmed scope, Timeline, Knock-on effects, What others are doing, Open questions. Cite every factual sentence.

## Negative rules
Never invent a figure, a date, or a quote. Separate confirmed facts from reported expectations and say which is which. If the event cannot be confirmed from a primary or reputable source, say so in the first sentence.`,
    DEEP_DIVE_GOALS,
  ),
  goals: DEEP_DIVE_GOALS,
  sources: {
    "prioritize": "Operators, regulators, port authorities, and company statements first; then local and regional news near the facility; then wires and trade press.",
    "avoid": "Content farms, AI-generated summary sites, forums, and undated pages."
  },
  output_schema: undefined,
  suggested_questions: [
    "Investigate: new Chinese export licensing rules on rare-earth magnets. Exposures: NdFeB rare-earth magnets (China) used in true-wireless earbuds.",
    "Investigate: a fire reported at a lithium-ion cell plant in Jiangsu, China. Exposures: lithium-ion cells (China) for a 14-inch ultrabook laptop.",
    "Investigate: congestion at the Port of Los Angeles/Long Beach this week. Exposures: ocean freight Kaohsiung to Los Angeles/Long Beach."
  ],
};
