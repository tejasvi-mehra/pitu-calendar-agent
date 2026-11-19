/**
 * Google Identity Services token client.
 *
 * The access token lives in a module variable only: never localStorage, never a
 * cookie, never rendered. Closing the tab ends it.
 */

type TokenResponse = { access_token?: string; error?: string; expires_in?: number };

type TokenClient = {
  requestAccessToken: (opts?: { prompt?: string }) => void;
};

declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initTokenClient: (cfg: {
            client_id: string;
            scope: string;
            callback: (r: TokenResponse) => void;
            error_callback?: (e: { message?: string }) => void;
          }) => TokenClient;
          revoke: (token: string, done?: () => void) => void;
        };
      };
    };
  }
}

export const SCOPES = "openid email https://www.googleapis.com/auth/calendar.events";

let token: string | null = null;
let clientId = "";
let ready: Promise<void> | null = null;

export function loadGis(): Promise<void> {
  if (ready) return ready;
  ready = new Promise<void>((resolve, reject) => {
    if (window.google?.accounts?.oauth2) return resolve();
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Could not load Google sign-in"));
    document.head.appendChild(s);
  });
  return ready;
}

export type Grant = { token: string; expiresIn: number };

export async function signIn(id: string): Promise<Grant> {
  clientId = id;
  await loadGis();
  return request("consent");
}

/**
 * Same flow, no consent screen when the user already granted the scopes.
 * Note: this still opens a popup. GIS has no background auth.
 */
export async function reauth(id: string): Promise<Grant> {
  clientId = id;
  await loadGis();
  return request("");
}

/** Resolves once the user completes the Google flow; always shows UI. */
export function request(prompt: "" | "consent"): Promise<Grant> {
  return new Promise<Grant>((resolve, reject) => {
    const client = window.google!.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: SCOPES,
      callback: (r) => {
        if (r.error || !r.access_token) return reject(new Error(r.error ?? "no token"));
        token = r.access_token;
        resolve({ token: r.access_token, expiresIn: r.expires_in ?? 3600 });
      },
      error_callback: (e) => reject(new Error(e.message ?? "sign-in failed")),
    });
    // "consent" forces the full scope list; "" can silently return only previously
    // granted scopes, which then 403s on calendar writes.
    client.requestAccessToken({ prompt });
  });
}

export function getToken(): string | null {
  return token;
}

export function setToken(value: string | null): void {
  token = value;
}

export function signOut(): void {
  if (token) window.google?.accounts.oauth2.revoke(token);
  token = null;
}
