import { describe, expect, it } from "vitest";
import { applyCoupon, lineTotal, subtotal, tax, total } from "./cart";

describe("cart", () => {
  it("subtotal sums lines", () => {
    expect(subtotal([{ sku: "a", price: 2, qty: 3 }])).toBe(6);
  });
  it("bulk discount starts at exactly 10", () => {
    expect(lineTotal({ sku: "a", price: 1, qty: 10 })).toBe(9);
  });
  it("fixed coupon never goes below zero", () => {
    expect(applyCoupon(5, { kind: "fixed", value: 8 })).toBe(0);
  });
  it("percent coupon respects maxOff", () => {
    expect(applyCoupon(200, { kind: "percent", value: 50, maxOff: 30 })).toBe(170);
  });
  it("unknown region throws", () => {
    expect(() => tax(10, "ZZ")).toThrow();
  });
  it("total rounds to cents", () => {
    expect(total([{ sku: "a", price: 0.1, qty: 3 }], "OR")).toBe(0.3);
  });
  it("CA tax on discounted amount", () => {
    expect(total([{ sku: "a", price: 100, qty: 1 }], "CA", { kind: "percent", value: 10 })).toBe(96.53);
  });
  it("total is computed in integer cents (no float drift on large carts)", () => {
    const items = Array.from({ length: 1000 }, (_, i) => ({ sku: `s${i}`, price: 0.07, qty: 1 }));
    expect(total(items, "NY")).toBe(72.8);
  });
});
