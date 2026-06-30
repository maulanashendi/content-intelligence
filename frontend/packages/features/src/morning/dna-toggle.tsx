interface DnaToggleProps {
  on: boolean
  onChange: (next: boolean) => void
}

export function DnaToggle({ on, onChange }: DnaToggleProps) {
  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      onChange(!on)
    }
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        onClick={() => onChange(!on)}
        onKeyDown={handleKeyDown}
        style={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
          width: 36,
          height: 20,
          borderRadius: 10,
          border: "none",
          cursor: "pointer",
          padding: 0,
          flexShrink: 0,
          background: on ? "var(--accent)" : "var(--bg-sunken)",
          outline: "none",
          transition: "background 0.15s",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 2,
            left: on ? 18 : 2,
            width: 16,
            height: 16,
            borderRadius: "50%",
            background: on ? "white" : "var(--line)",
            "@media (prefers-reduced-motion: no-preference)": undefined,
            transition: "left 0.15s",
          } as React.CSSProperties}
        />
        <style>{`
          @media (prefers-reduced-motion: reduce) {
            [role="switch"] span { transition: none !important; }
          }
        `}</style>
      </button>
      <span style={{ fontSize: 12.5, color: "var(--fg-muted)", userSelect: "none" }}>
        Tema Tempo
      </span>
    </div>
  )
}
