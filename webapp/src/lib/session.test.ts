import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearToken, readToken, writeToken } from "./session";

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
  vi.stubGlobal("sessionStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  });
});

describe("token cache", () => {
  it("round-trips a token before expiry", () => {
    writeToken("ya29.abc", 3600);
    expect(readToken()?.token).toBe("ya29.abc");
  });

  it("returns null once expired", () => {
    writeToken("ya29.abc", 3600);
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 3601 * 1000);
    expect(readToken()).toBeNull();
    vi.restoreAllMocks();
  });

  it("treats a token inside the skew window as expired", () => {
    writeToken("ya29.abc", 3600);
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 3599 * 1000);
    expect(readToken()).toBeNull();
    vi.restoreAllMocks();
  });

  it("returns null when nothing was stored", () => {
    expect(readToken()).toBeNull();
  });

  it("clearToken removes both keys", () => {
    writeToken("ya29.abc", 3600);
    clearToken();
    expect(store.size).toBe(0);
  });
});
