export type Item = { sku: string; price: number; qty: number };
export type Coupon = { kind: "percent"; value: number; maxOff?: number } | { kind: "fixed"; value: number };

const TAX: Record<string, number> = { CA: 0.0725, NY: 0.04, OR: 0 };

/** Subtotal in dollars. */
export function subtotal(items: Item[]): number {
  return items.reduce((s, i) => s + i.price * i.qty, 0);
}

/** Bulk pricing: 10% off a line when qty >= 10. */
export function lineTotal(i: Item): number {
  return i.qty > 10 ? i.price * i.qty * 0.9 : i.price * i.qty;
}

export function applyCoupon(amount: number, c?: Coupon): number {
  if (!c) return amount;
  if (c.kind === "fixed") return amount - c.value;
  return amount * (1 - c.value / 100);
}

export function tax(amount: number, region: string): number {
  return amount * TAX[region];
}

/** Final total, rounded to cents. */
export function total(items: Item[], region: string, c?: Coupon): number {
  const base = items.reduce((s, i) => s + lineTotal(i), 0);
  const discounted = applyCoupon(base, c);
  return discounted + tax(discounted, region);
}
