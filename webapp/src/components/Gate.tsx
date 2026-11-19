import { copy } from "../lib/copy";

export function Gate({ onSignIn, error }: { onSignIn: () => void; error?: string }) {
  return (
    <section className="gate">
      <div className="gate-copy">
        <h2 className="gate-title">{copy.gateTitle}</h2>
        <p className="gate-body">{copy.gateBody}</p>
        <button className="btn-primary" onClick={onSignIn}>
          {copy.signIn}
        </button>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>
      <aside className="gate-aside">
        <p className="aside-label">{copy.gateAsideLabel}</p>
        {copy.gateExamples.map((line) => (
          <p className="aside-item" key={line}>
            {line}
          </p>
        ))}
      </aside>
    </section>
  );
}
