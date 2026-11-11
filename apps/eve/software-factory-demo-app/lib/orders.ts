export type Order = {
  id: string;
  status: "processing" | "shipped" | "delivered" | "refunded";
  item: string;
  total: number;
};

const ORDERS: Record<string, Order> = {
  "A-1001": { id: "A-1001", status: "shipped", item: "Mechanical keyboard", total: 129 },
  "A-1002": { id: "A-1002", status: "processing", item: "USB-C dock", total: 89 },
  "A-1003": { id: "A-1003", status: "refunded", item: "Monitor arm", total: 59 },
};

export function findOrder(id: string): Order | undefined {
  return ORDERS[id.trim().toUpperCase()];
}
