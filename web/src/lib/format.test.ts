import { describe, expect, it } from "vitest";
import { shopName } from "./format";

describe("shopName", () => {
  it("names each company once, without the country suffix", () => {
    expect(shopName("idealo_at")).toBe("Idealo");
    expect(shopName("geizhals_at, idealo_at")).toBe("Geizhals, Idealo");
    expect(shopName("geizhals, geizhals_at")).toBe("Geizhals");
    expect(shopName("amazon_de")).toBe("Amazon");
    expect(shopName(null)).toBe("");
  });
});
