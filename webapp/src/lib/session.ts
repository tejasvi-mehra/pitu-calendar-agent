/**
 * Session-scoped token cache.
 *
 * GIS has no silent auth: requestAccessToken() always opens a popup. So the token
 * is kept in sessionStorage (cleared on tab close) with its expiry, and re-requested
 * only when it is gone or near expiry.
 *
 * Security: sessionStorage is readable by injected script. Mitigations: 1-hour expiry
 * enforced client-side, cleared on sign-out, tab-scoped, and the server re-verifies
 * every token against Google's tokeninfo on every request (I8).
 */
const TOKEN_KEY = "pitu.token";
const EXP_KEY = "pitu.expires";
const SKEW_MS = 60_000; // refresh a minute early so a request never races expiry

export type Cached = { token: string; expiresAt: number };

export function readToken(): Cached | null {
  try {
    const token = sessionStorage.getItem(TOKEN_KEY);
    const exp = Number(sessionStorage.getItem(EXP_KEY));
    if (!token || !exp) return null;
    if (Date.now() > exp - SKEW_MS) return null;
    return { token, expiresAt: exp };
  } catch {
    return null;
  }
}

export function writeToken(token: string, expiresInSeconds: number): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(EXP_KEY, String(Date.now() + expiresInSeconds * 1000));
  } catch {
    /* storage unavailable; the session lasts until refresh */
  }
}

export function clearToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(EXP_KEY);
  } catch {
    /* nothing to clear */
  }
}

/** The non-secret "stay signed in across reloads" flag for the gate and email. */
const FLAG = "pitu.autologin";
const EMAIL_KEY = "pitu.email";

export const remember = (): void => {
  try {
    localStorage.setItem(FLAG, "1");
  } catch {
    /* storage unavailable */
  }
};

export const remembered = (): boolean => {
  try {
    return localStorage.getItem(FLAG) === "1";
  } catch {
    return false;
  }
};

export const forget = (): void => {
  try {
    localStorage.removeItem(FLAG);
  } catch {
    /* nothing to clear */
  }
};

export const savedEmail = (): string | null => {
  try {
    return localStorage.getItem(EMAIL_KEY);
  } catch {
    return null;
  }
};

export const saveEmail = (email: string): void => {
  try {
    localStorage.setItem(EMAIL_KEY, email);
  } catch {
    /* the chip falls back to an initial */
  }
};
