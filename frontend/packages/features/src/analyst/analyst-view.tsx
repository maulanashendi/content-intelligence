import { useState, useRef, useEffect } from "react"
import { isApiError } from "@ei-fe/core"
import { useAnalyzeArticle, useRecommendation } from "@ei-fe/api"
import type { AnalyzeResult, RecommendationOutput } from "@ei-fe/api"
import { Bot, Sparkles, Plus } from "@ei-fe/ui"
import { UserBubble } from "./message-bubble.js"
import { Composer, type Mode, type SubmitPayload } from "./composer.js"
import { AnalyzeResultCard } from "./analyze-result.js"
import { RecommendationResultCard } from "./recommendation-result.js"

type Msg =
  | { id: string; role: "user"; command: string; text: string; payload: SubmitPayload }
  | { id: string; role: "analyze"; title: string; data: AnalyzeResult }
  | { id: string; role: "reco"; data: RecommendationOutput }
  | { id: string; role: "error"; text: string }
  | { id: string; role: "loading" }

let seq = 0
const nextId = () => `m${seq++}`

const SUGGESTIONS = [
  { mode: "analyze" as Mode, title: "Analisis draf", text: "Tempel judul + isi artikel untuk skor 16 fitur, kebutuhan pembaca, dan masukan editorial." },
  { mode: "recommendation" as Mode, title: "Performa minggu ini", text: "Artikel ekonomi paling banyak dibaca minggu ini, dan apa yang harus ditulis berikutnya?" },
]

export function AnalystView({ initialTitle, initialMode }: { initialTitle?: string; initialMode?: Mode }) {
  const [messages, setMessages] = useState<Msg[]>([])
  const [mode, setMode] = useState<Mode>(initialMode ?? "analyze")
  const scrollRef = useRef<HTMLDivElement>(null)
  const analyze = useAnalyzeArticle()
  const reco = useRecommendation()
  const busy = analyze.isPending || reco.isPending

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages])

  function push(m: Omit<Msg, "id">) { setMessages((p) => [...p, { ...m, id: nextId() } as Msg]) }
  function replaceLoading(m: Omit<Msg, "id">) {
    setMessages((p) => { const out = p.filter((x) => x.role !== "loading"); return [...out, { ...m, id: nextId() } as Msg] })
  }

  async function handleSubmit(p: SubmitPayload) {
    if (p.kind === "analyze") {
      push({ role: "user", command: "/analyze · draf artikel", text: p.title, payload: p })
      push({ role: "loading" })
      try {
        const data = await analyze.mutateAsync({ title: p.title, content: p.content })
        replaceLoading({ role: "analyze", title: p.title, data })
      } catch (e) {
        replaceLoading({ role: "error", text: isApiError(e) ? e.message : "Analisis gagal. Coba lagi." })
      }
    } else {
      push({ role: "user", command: "/recommendation", text: p.intent, payload: p })
      push({ role: "loading" })
      try {
        const data = await reco.mutateAsync(p.intent)
        replaceLoading({ role: "reco", data })
      } catch (e) {
        replaceLoading({ role: "error", text: isApiError(e) ? e.message : "Rekomendasi gagal. Coba lagi." })
      }
    }
  }

  const empty = messages.length === 0

  return (
    <div className="flex flex-col min-h-0 flex-1" style={{ background: "var(--bg)" }}>
      <header className="flex items-center gap-3 px-7 py-4" style={{ borderBottom: "1px solid var(--line)", background: "var(--bg-elev)" }}>
        <span className="w-[34px] h-[34px] rounded-[9px] grid place-items-center shrink-0" style={{ background: "linear-gradient(135deg, var(--accent), oklch(0.45 0.18 285))", color: "white" }}><Sparkles size={17} /></span>
        <div>
          <div className="text-[15px] font-semibold tracking-tight">AI Analyst</div>
          <div className="text-[11.5px]" style={{ color: "var(--fg-muted)" }}>Asisten redaksi · analisis draf &amp; rekomendasi performa</div>
        </div>
        <span className="flex-1" />
        {!empty && (
          <button onClick={() => setMessages([])} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[6px] text-[12.5px]" style={{ color: "var(--fg-muted)", border: "1px solid var(--line)" }}>
            <Plus size={14} /> Analisis baru
          </button>
        )}
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[860px] px-6 py-7 flex flex-col gap-6">
          {empty ? (
            <div className="flex flex-col items-center gap-6 py-10 text-center">
              <span className="w-14 h-14 rounded-[16px] grid place-items-center" style={{ background: "var(--accent-soft)", color: "var(--accent-fg)" }}><Sparkles size={26} /></span>
              <div>
                <h2 className="text-[20px] font-semibold tracking-tight m-0">Apa yang bisa saya bantu?</h2>
                <p className="text-[13px] mt-1.5 m-0" style={{ color: "var(--fg-muted)" }}>Analisis draf sebelum terbit, atau minta rekomendasi dari data performa.</p>
              </div>
              <div className="grid gap-3 w-full max-w-xl" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                {SUGGESTIONS.map((s) => (
                  <button key={s.title} onClick={() => setMode(s.mode)} className="text-left rounded-[10px] p-3.5" style={{ background: "var(--bg-elev)", border: "1px solid var(--line)" }}>
                    <span className="block text-[13px] font-medium">{s.title}</span>
                    <span className="block text-[12px] mt-1" style={{ color: "var(--fg-muted)" }}>{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => {
              if (m.role === "user") return <UserBubble key={m.id} command={m.command} text={m.text} />
              if (m.role === "loading") return <BotRow key={m.id}><LoadingDots /></BotRow>
              if (m.role === "error") {
                const idx = messages.indexOf(m)
                const prevUser = messages.slice(0, idx).reverse().find((x) => x.role === "user")
                return (
                  <BotRow key={m.id}>
                    <div role="alert" className="rounded-[10px] p-3.5" style={{ background: "var(--bad-soft)", border: "1px solid oklch(0.58 0.18 25 / 0.25)" }}>
                      <p className="text-[13px] m-0" style={{ color: "var(--bad)" }}>{m.text}</p>
                      {prevUser && prevUser.role === "user" && (
                        <button onClick={() => handleSubmit(prevUser.payload)} disabled={busy}
                          className="mt-2 text-[12px] px-2.5 py-1 rounded-[6px]"
                          style={{ color: "var(--bad)", border: "1px solid oklch(0.58 0.18 25 / 0.35)" }}>
                          Coba lagi
                        </button>
                      )}
                    </div>
                  </BotRow>
                )
              }
              if (m.role === "analyze") return <BotRow key={m.id}><AnalyzeResultCard title={m.title} result={m.data} /></BotRow>
              return <BotRow key={m.id}><RecommendationResultCard result={m.data} /></BotRow>
            })
          )}
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--line)", background: "var(--bg-elev)" }}>
        <div className="mx-auto max-w-[860px] px-6 py-3.5">
          <Composer mode={mode} onModeChange={setMode} onSubmit={handleSubmit} disabled={busy} initialText={initialTitle} />
        </div>
      </div>
    </div>
  )
}

function BotRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="w-7 h-7 rounded-[8px] grid place-items-center shrink-0 mt-0.5" style={{ background: "var(--accent-soft)", color: "var(--accent-fg)" }}><Bot size={15} /></span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  )
}

function LoadingDots() {
  return (
    <div className="inline-flex items-center gap-1.5 px-3.5 py-3 rounded-[10px]" style={{ background: "var(--bg-sunken)" }}>
      {[0, 1, 2].map((i) => (
        <span key={i} className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--fg-ghost)", animation: `analystPulse 1.2s ${i * 0.15}s infinite ease-in-out` }} />
      ))}
    </div>
  )
}
