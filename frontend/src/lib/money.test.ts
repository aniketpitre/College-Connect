import { describe, expect, it } from "vitest";
import { formatPaise, paiseToInput, parseRupees } from "./money";

describe("money", () => {
  it("parses rupees into paise without floating point", () => {
    expect(parseRupees("12,500.50")).toBe(1250050);
    expect(parseRupees("₹ 0.1")).toBe(10);
    expect(parseRupees("19.99")).toBe(1999);
    expect(parseRupees("1.005")).toBeNull();
    expect(parseRupees("abc")).toBeNull();
    expect(parseRupees("")).toBeNull();
  });
  it("round-trips through the input box", () => {
    expect(paiseToInput(1250050)).toBe("12500.50");
    expect(paiseToInput(100)).toBe("1");
    expect(parseRupees(paiseToInput(1999))).toBe(1999);
  });
  it("formats Indian grouping", () => {
    expect(formatPaise(12500000)).toBe("₹1,25,000.00");
  });
});
