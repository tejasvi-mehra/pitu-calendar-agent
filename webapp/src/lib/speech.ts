/** Browser speech: recognition in, synthesis out. Both degrade to no-ops. */

type Result = { 0: { transcript: string }; isFinal: boolean };
type Event = { resultIndex: number; results: { length: number } & Record<number, Result> };

interface SpeechRec {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: Event) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

type Ctor = new () => SpeechRec;

function ctor(): Ctor | undefined {
  const w = window as unknown as { SpeechRecognition?: Ctor; webkitSpeechRecognition?: Ctor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

export const speechSupported = (): boolean => Boolean(ctor());

export function listen(onFinal: (text: string) => void, onEnd: () => void): () => void {
  const C = ctor();
  if (!C) {
    onEnd();
    return () => {};
  }
  const rec = new C();
  rec.lang = navigator.language || "en-US";
  rec.interimResults = true;
  rec.continuous = true; // continuous=false ends on the first pause
  rec.onresult = (e) => {
    let text = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) text += e.results[i][0].transcript;
    }
    if (text.trim()) onFinal(text.trim());
  };
  rec.onend = onEnd;
  rec.onerror = onEnd;
  rec.start();
  return () => {
    rec.onend = null;
    rec.onerror = null;
    rec.stop();
  };
}

export interface VoiceOption {
  name: string;
  lang: string;
}

/** Human-sounding engines first: local/system voices and the newer natural ones. */
export function voices(): VoiceOption[] {
  if (!("speechSynthesis" in window)) return [];
  return window.speechSynthesis
    .getVoices()
    .filter((v) => v.lang.startsWith("en"))
    .map((v) => ({ name: v.name, lang: v.lang }));
}

export function stopSpeaking(): void {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

export function speak(text: string, voiceName?: string): void {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  if (voiceName) {
    const match = window.speechSynthesis.getVoices().find((v) => v.name === voiceName);
    if (match) u.voice = match;
  }
  u.rate = 1;
  u.pitch = 1;
  // Chrome drops an utterance queued too soon after cancel()
  window.speechSynthesis.cancel();
  setTimeout(() => window.speechSynthesis.speak(u), 60);
}
