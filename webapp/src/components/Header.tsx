import { copy } from "../lib/copy";
import { AccountChip } from "./AccountChip";

export function Header({
  email,
  voice,
  onVoice,
  onSignIn,
  onSignOut,
}: {
  email: string | null;
  voice: string;
  onVoice: (name: string) => void;
  onSignIn: () => void;
  onSignOut: () => void;
}) {
  return (
    <header className="header">
      <h1 className="wordmark">
        <img className="mark" src="/logo.png" alt="" width={28} height={29} />
        {copy.wordmark}
      </h1>
      <AccountChip
        email={email}
        voice={voice}
        onVoice={onVoice}
        onSignIn={onSignIn}
        onSignOut={onSignOut}
      />
    </header>
  );
}
