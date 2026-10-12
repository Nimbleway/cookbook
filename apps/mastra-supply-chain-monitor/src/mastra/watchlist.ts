// The products this monitor watches, and the exposures that make up each supply chain.
// Exposure strings are sent to the sweep agent verbatim and come back verbatim in
// `affected_exposures`, which is how an event is matched to every product it touches.
// `singleSource` marks exposures with no qualified alternative: the triage rubric weighs
// those higher.

export type Exposure = { name: string; singleSource: boolean };
export type Product = { slug: string; name: string; exposures: Exposure[] };

export const WATCHLIST: Product[] = [
  {
    slug: "laptop",
    name: "14-inch ultrabook laptop",
    exposures: [
      { name: "TSMC (Taiwan) CPUs", singleSource: true },
      { name: "Samsung and SK hynix (South Korea) DRAM and NAND", singleSource: false },
      { name: "lithium-ion cells (China)", singleSource: false },
      { name: "NdFeB rare-earth magnets (China)", singleSource: true },
      { name: "final assembly in Chongqing, China", singleSource: true },
      { name: "ocean freight Kaohsiung to Los Angeles/Long Beach", singleSource: false },
    ],
  },
  {
    slug: "earbuds",
    name: "true-wireless earbuds",
    exposures: [
      { name: "Bluetooth SoC (TSMC, Taiwan)", singleSource: true },
      { name: "NdFeB rare-earth magnets (China)", singleSource: true },
      { name: "lithium-ion coin cells (China)", singleSource: false },
      { name: "final assembly in Bac Ninh, Vietnam", singleSource: true },
      { name: "air freight Hanoi to Los Angeles", singleSource: false },
    ],
  },
  {
    slug: "smartwatch",
    name: "smartwatch",
    exposures: [
      { name: "application processor (TSMC, Taiwan)", singleSource: true },
      { name: "OLED display (Samsung Display, South Korea)", singleSource: true },
      { name: "lithium-ion cells (China)", singleSource: false },
      { name: "final assembly in Bac Ninh, Vietnam", singleSource: true },
      { name: "air freight Hanoi to Los Angeles", singleSource: false },
    ],
  },
];

export function productBySlug(slug: string): Product | undefined {
  return WATCHLIST.find((p) => p.slug === slug);
}

// Every product whose exposure list contains one of these exposure names.
export function productsTouchedBy(exposureNames: string[]): string[] {
  const wanted = new Set(exposureNames.map((e) => e.trim().toLowerCase()));
  return WATCHLIST.filter((p) => p.exposures.some((e) => wanted.has(e.name.toLowerCase()))).map((p) => p.slug);
}
