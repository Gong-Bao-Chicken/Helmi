import { describe, expect, it } from "vitest";
import { priceWindowLabel, shopName } from "./format";

describe("shopName", () => {
  it("names each company once, without the country suffix", () => {
    expect(shopName("idealo_at")).toBe("Idealo");
    expect(shopName("geizhals_at, idealo_at")).toBe("Geizhals, Idealo");
    expect(shopName("geizhals, geizhals_at")).toBe("Geizhals");
    expect(shopName("amazon_de")).toBe("Amazon");
    expect(shopName(null)).toBe("");
  });
});

describe("priceWindowLabel", () => {
  it("names the pipeline's price windows", () => {
    expect(priceWindowLabel("30d_median")).toBe("30-day median");
    expect(priceWindowLabel("14d_median")).toBe("14-day median");
    expect(priceWindowLabel("30d_latest")).toBe("latest price");
    expect(priceWindowLabel(null)).toBeNull();
  });
});
