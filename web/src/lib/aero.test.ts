import { describe, expect, it } from "vitest";
import { timeSaved } from "./aero";
import type { AeroSourceResult } from "./types";

const src = (watts_saved: number, error_margin_w = 0.7) =>
  ({ source: "x", watts_saved, drag_watts_40kph: 250, error_margin_w }) as AeroSourceResult;

describe("timeSaved", () => {
  it("turns a watt saving into seconds at constant power", () => {
    // 6 W of 250 W over an hour at 40 km/h: about 29 s.
    expect(timeSaved(src(6), 40, 40)!.seconds).toBeCloseTo(29.1, 0);
    expect(timeSaved(src(-6), 40, 40)!.seconds).toBeLessThan(0);
  });

  it("flags differences within the test's error margin", () => {
    expect(timeSaved(src(0.5), 40, 40)!.withinError).toBe(true);
    expect(timeSaved(src(3), 40, 40)!.withinError).toBe(false);
  });
});
