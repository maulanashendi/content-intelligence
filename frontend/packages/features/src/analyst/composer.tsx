import { useEffect, useState, type KeyboardEvent } from "react"
import { Sparkles, BarChart3, ArrowUp } from "@ei-fe/ui"

export type Mode = "analyze" | "recommendation"
export type SubmitPayload =
  | { kind: "analyze"; title: string; content: string }
  | { kind: "recommendation"; intent: string }

export function Composer({ mode, onModeChange, onSubmit, disabled, initialText, seedText, onSeedConsumed }: {
  mode: Mode
  onModeChange: (m: Mode) => void
  onSubmit: (p: SubmitPayload) => void
  disabled: boolean
  initialText?: string
  /** When set, the composer replaces its current text with this value and notifies the parent via onSeedConsumed. */
  seedText?: string
  onSeedConsumed?: () => void
}) {
  const [text, setText] = useState(initialText ?? "")
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (seedText !== undefined) {
      setText(seedText)
      setError(null)
      onSeedConsumed?.()
    }
  }, [seedText]) // intentionally omit onSeedConsumed to avoid re-triggering on parent re-render

  function submit() {
    const value = text.trim()
    if (!value || disabled) return
    if (mode === "analyze") {
      const [firstLine, ...rest] = value.split("\n")
      if (firstLine === undefined) return
      const title = firstLine.trim().slice(0, 200)
      const content = (rest.join("\n").trim() || firstLine).slice(0, 20000)
      if (content.length < 1) { setError("Tempel isi draf untuk dianalisis."); return }
      onSubmit({ kind: "analyze", title: title || "Draf tanpa judul", content })
    } else {
      if (value.length < 3) { setError("Jelaskan yang ingin dianalisis (min. 3 karakter)."); return }
      onSubmit({ kind: "recommendation", intent: value.slice(0, 500) })
    }
    setText("")
    setError(null)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit() }
  }

  const modes: { id: Mode; label: string; Icon: typeof Sparkles }[] = [
    { id: "analyze", label: "Analisis Artikel", Icon: Sparkles },
    { id: "recommendation", label: "Rekomendasi", Icon: BarChart3 },
  ]

  return (
    <div>
      <div className="inline-flex gap-0.5 p-0.5 rounded-[8px] mb-2.5" style={{ background: "var(--bg-sunken)", border: "1px solid var(--line)" }}>
        {modes.map((m) => {
          const active = mode === m.id
          return (
            <button key={m.id} type="button" onClick={() => { onModeChange(m.id); setError(null) }}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[6px] text-[12px]"
              style={active ? { background: "var(--bg-elev)", color: "var(--fg)", boxShadow: "var(--shadow-sm)", fontWeight: 500 } : { color: "var(--fg-muted)" }}>
              <m.Icon size={13} />{m.label}
            </button>
          )
        })}
      </div>
      <div className="flex items-end gap-2 p-2.5 rounded-[12px]" style={{ background: "var(--bg-elev)", border: "1px solid var(--line-strong)", boxShadow: "var(--shadow-sm)" }}>
        <textarea
          value={text}
          onChange={(e) => { setText(e.target.value); if (error) setError(null) }}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder={mode === "analyze" ? "Tempel judul + isi draf untuk dianalisis…" : "Mis. artikel ekonomi paling banyak dibaca minggu ini…"}
          aria-label={mode === "analyze" ? "Tempel judul dan isi draf untuk dianalisis" : "Tulis permintaan rekomendasi"}
          className="flex-1 resize-none bg-transparent border-0 outline-none text-[13px] leading-normal max-h-40"
          style={{ color: "var(--fg)" }}
        />
        <button type="button" onClick={submit} disabled={disabled || !text.trim()} aria-label="Kirim"
          className="w-8 h-8 rounded-[8px] grid place-items-center shrink-0 disabled:opacity-40"
          style={{ background: "var(--accent)", color: "white" }}>
          <ArrowUp size={16} />
        </button>
      </div>
      {error && <p className="text-[11.5px] mt-1.5" role="alert" style={{ color: "var(--bad)" }}>{error}</p>}
      <p className="text-center text-[10.5px] mt-2" style={{ color: "var(--fg-faint)" }}>AI Analyst memberi masukan editorial dari fitur konten &amp; data performa historis.</p>
    </div>
  )
}
