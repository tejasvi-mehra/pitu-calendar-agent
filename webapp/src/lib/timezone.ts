/**
 * Reads the browser's IANA zone and applies a user override.
 * An override wins; anything empty falls back to the browser zone, then UTC.
 */
export function resolveTimezone(
  browserZone: string | undefined,
  override: string,
): string {
  const trimmed = (override ?? "").trim();
  if (trimmed) return trimmed;
  const browser = (browserZone ?? "").trim();
  if (browser) return browser;
  return "UTC";
}

export function detectBrowserZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return undefined;
  }
}
