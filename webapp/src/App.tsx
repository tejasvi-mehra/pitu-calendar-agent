import { useCallback, useEffect, useRef, useState } from "react";
import { getToken, reauth, setToken as setAuthToken, signIn, signOut } from "./lib/auth";
import { copy } from "./lib/copy";
import {
  clearToken,
  forget,
  readToken,
  remember,
  remembered,
  saveEmail,
  savedEmail,
  writeToken,
} from "./lib/session";
import { listen, speak, stopSpeaking, speechSupported } from "./lib/speech";
import { detectBrowserZone, resolveTimezone } from "./lib/timezone";
import type { Turn } from "./lib/types";
import { Header } from "./components/Header";
import { Gate } from "./components/Gate";
import { History } from "./components/History";
import { Composer } from "./components/Composer";

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";
const MAX_TURNS = 50;

export default function App() {
  // restore from sessionStorage first: no popup, no network, survives a refresh
  const cached = readToken();
  if (cached) setAuthToken(cached.token);
  const [token, setToken] = useState<string | null>(cached?.token ?? getToken());
  const [email, setEmail] = useState<string | null>(savedEmail);
  const [restoring, setRestoring] = useState(() => !getToken() && remembered());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const [override, setOverride] = useState("");
  const [tzEditing, setTzEditing] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);
  const [speakNext, setSpeakNext] = useState(false);
  const [voice, setVoice] = useState<string>(() => {
    try {
      return localStorage.getItem("pitu.voice") ?? "";
    } catch {
      return "";
    }
  });
  const stopRef = useRef<(() => void) | null>(null);

  const tz = resolveTimezone(detectBrowserZone(), override);

  // clear the speaking marker when synthesis ends on its own
  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const id = setInterval(() => {
      if (!window.speechSynthesis.speaking) setSpeakingIndex(null);
    }, 500);
    return () => clearInterval(id);
  }, []);

  // Re-auth only when the cached token is gone: GIS has no silent mode, so this
  // always shows UI. Deferred a moment so a first-visit gate is not hidden.
  useEffect(() => {
    if (!restoring) return;
    let cancelled = false;
    reauth(CLIENT_ID)
      .then(async ({ token: t, expiresIn }) => {
        const r = await fetch("/me", { headers: { Authorization: `Bearer ${t}` } });
        if (cancelled) return;
        if (!r.ok) throw new Error("restore rejected");
        const data = await r.json();
        if (!String(data.scope ?? "").includes("calendar.events")) {
          throw new Error("scope missing");
        }
        setAuthToken(t);
        writeToken(t, expiresIn);
        setToken(t);
        if (data.email) {
          setEmail(data.email);
          saveEmail(data.email);
        }
      })
      .catch(() => {
        /* user dismissed the popup; the gate is showing */
      })
      .finally(() => {
        if (!cancelled) setRestoring(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSignIn() {
    setError("");
    try {
      const { token: t, expiresIn } = await signIn(CLIENT_ID);
      setAuthToken(t);
      writeToken(t, expiresIn);
      setToken(t);
      remember();
      const [health, meRes] = await Promise.all([
        fetch("/health"),
        fetch("/me", { headers: { Authorization: `Bearer ${t}` } }),
      ]);
      if (!health.ok) throw new Error(copy.offline);
      if (meRes.ok) {
        const { email: e } = await meRes.json();
        if (e) {
          setEmail(e);
          saveEmail(e);
        }
      }
    } catch (e) {
      setError(e instanceof Error && e.message === copy.offline ? copy.offline : copy.signInCancelled);
    }
  }

  function handleSignOut() {
    signOut();
    clearToken();
    forget();
    stopSpeaking();
    setSpeakingIndex(null);
    setToken(null);
    setTurns([]);
    setError("");
    setSpeakNext(false);
    setEmail(null);
  }

  function onMic() {
    if (listening) {
      stopRef.current?.();
      setListening(false);
      return;
    }
    if (!speechSupported()) return;
    setListening(true);
    stopRef.current = listen(
      (final) => setText((prev) => (prev ? `${prev} ${final}` : final)),
      () => setListening(false),
    );
  }

  function pickVoice(name: string) {
    setVoice(name);
    try {
      localStorage.setItem("pitu.voice", name);
    } catch {
      /* storage unavailable; the choice just won't persist */
    }
    // hear it before it matters
    speak("Hi, this is how I sound.", name || undefined);
    setSpeakingIndex(-1);
  }

  const speakTurn = useCallback(
    (index: number) => {
      const turn = turns[index];
      if (!turn) return;
      speak(turn.text, voice || undefined);
      setSpeakingIndex(index);
    },
    [turns, voice],
  );

  async function send() {
    const t = getToken();
    const request = text.trim();
    if (!t || !request || busy) return;
    setBusy(true);
    setError("");
    setText("");
    const at = Date.now();
    const userTurn: Turn = { role: "user", text: request, at };
    setTurns((prev) => [...prev.slice(-(MAX_TURNS - 1)), userTurn]);
    try {
      const r = await fetch("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${t}`,
          "X-Timezone": tz,
        },
        body: JSON.stringify({ text: request }),
      });
      const data = await r.json().catch(() => ({}));
      if (r.status === 401) {
        clearToken();
        forget();
        setToken(null);
        setEmail(null);
        setError(copy.sessionExpired);
        return;
      }
      if (r.status === 403 && String(data.detail ?? "").includes("Sign out")) {
        setError(String(data.detail));
        return;
      }
      if (!r.ok) {
        setError(copy.genericError);
        return;
      }
      const reply = String(data.reply ?? "");
      const replyTurn: Turn = { role: "assistant", text: reply, at: Date.now() };
      setTurns((prev) => [...prev, replyTurn].slice(-MAX_TURNS));
      if (speakNext) {
        speak(reply, voice || undefined);
        setSpeakNext(false);
      }
    } catch {
      setError(copy.offline);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <Header
        email={token ? email ?? "•" : null}
        voice={voice}
        onVoice={pickVoice}
        onSignIn={handleSignIn}
        onSignOut={handleSignOut}
      />

      {restoring ? (
        <section className="history" aria-busy="true" />
      ) : !token ? (
        <Gate onSignIn={handleSignIn} error={error} />
      ) : (
        <>
          <History
            turns={turns}
            speakingIndex={speakingIndex}
            onSpeak={(i) => {
              speakTurn(i);
              setSpeakNext(true);
            }}
            onStop={() => {
              stopSpeaking();
              setSpeakingIndex(null);
            }}
          />
          {error && (
            <div className="error" role="alert">
              <p>{error}</p>
            </div>
          )}
          <Composer
            value={text}
            onChange={setText}
            onSubmit={send}
            onMic={onMic}
            listening={listening}
            micSupported={speechSupported()}
            busy={busy}
            tz={tz}
            tzEditing={tzEditing}
            onTzEdit={() => setTzEditing((v) => !v)}
            onTzChange={(z) => {
              setOverride(z);
              setTzEditing(false);
            }}
          />
        </>
      )}
    </div>
  );
}
