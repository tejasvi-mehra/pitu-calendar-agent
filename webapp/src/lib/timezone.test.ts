import { describe, expect, it } from "vitest";
import { resolveTimezone } from "./timezone";

describe("resolveTimezone", () => {
  it("uses the browser zone when there is no override", () => {
    expect(resolveTimezone("Europe/London", "")).toBe("Europe/London");
  });

  it("lets the override win", () => {
    expect(resolveTimezone("Europe/London", "Asia/Singapore")).toBe("Asia/Singapore");
  });

  it("ignores a whitespace-only override", () => {
    expect(resolveTimezone("Europe/London", "   ")).toBe("Europe/London");
  });

  it("falls back to UTC when the browser zone is missing", () => {
    expect(resolveTimezone(undefined, "")).toBe("UTC");
  });
});
