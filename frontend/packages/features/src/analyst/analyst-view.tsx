import { useState, useRef, useEffect } from "react"
import { isApiError } from "@ei-fe/core"
import { useAnalyzeArticle, useRecommendation } from "@ei-fe/api"
import type { AnalyzeResult, RecommendationOutput } from "@ei-fe/api"
import { Sparkles, BarChart3, Plus } from "@ei-fe/ui"
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

type DistributiveOmit<T, K extends keyof never> = T extends unknown ? Omit<T, K> : never

let seq = 0
const nextId = () => `m${seq++}`

const ANALYZE_EXAMPLE = `Sri Mulyani umumkan paket stimulus fiskal baru\nMenteri Keuangan mengumumkan paket stimulus Rp150 triliun untuk mendorong pertumbuhan ekonomi kuartal mendatang.`
const RECO_EXAMPLE = `Artikel ekonomi paling banyak dibaca minggu ini, lalu apa yang harus ditulis berikutnya?`

export function AnalystView({ initialTitle, initialMode }: { initialTitle?: string; initialMode?: Mode }) {
  const [messages, setMessages] = useState<Msg[]>([])
  const [mode, setMode] = useState<Mode>(initialMode ?? "analyze")
  const [seedText, setSeedText] = useState<string | undefined>(undefined)
  const scrollRef = useRef<HTMLDivElement>(null)
  const analyze = useAnalyzeArticle()
  const reco = useRecommendation()
  const busy = analyze.isPending || reco.isPending

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages])

  function push(m: DistributiveOmit<Msg, "id">) { setMessages((p) => [...p, { ...m, id: nextId() } as Msg]) }
  function replaceLoading(m: DistributiveOmit<Msg, "id">) {
    setMessages((p) => { const out = p.filter((x) => x.role !== "loading"); return [...out, { ...m, id: nextId() } as Msg] })
  }

  async function handleSubmit(p: SubmitPayload) {
    if (p.kind === "analyze") {
      push({ role: "user", command: "Analisis draf", text: p.title, payload: p })
      push({ role: "loading" })
      try {
        const data = await analyze.mutateAsync({ title: p.title, content: p.content })
        replaceLoading({ role: "analyze", title: p.title, data })
      } catch (e) {
        replaceLoading({ role: "error", text: isApiError(e) ? e.message : "Analisis gagal. Coba lagi." })
      }
    } else {
      push({ role: "user", command: "Rekomendasi", text: p.intent, payload: p })
      push({ role: "loading" })
      try {
        const data = await reco.mutateAsync(p.intent)
        replaceLoading({ role: "reco", data })
      } catch (e) {
        replaceLoading({ role: "error", text: isApiError(e) ? e.message : "Rekomendasi gagal. Coba lagi." })
      }
    }
  }

  function prefill(targetMode: Mode, text: string) {
    setMode(targetMode)
    setSeedText(text)
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
        <div className={`mx-auto max-w-[860px] px-6 py-7 flex flex-col ${empty ? "min-h-full justify-center" : ""}`} style={{ gap: "26px" }}>
          {empty ? (
            <EmptyState onPrefill={prefill} />
          ) : (
            messages.map((m) => {
              if (m.role === "user") return <UserBubble key={m.id} command={m.command} text={m.text} />
              if (m.role === "loading") return <LoadingSkeleton key={m.id} />
              if (m.role === "error") {
                const idx = messages.indexOf(m)
                const prevUser = messages.slice(0, idx).reverse().find((x) => x.role === "user")
                return (
                  <div key={m.id} role="alert" className="rounded-[10px] p-3.5" style={{ background: "var(--bad-soft)", border: "1px solid oklch(0.58 0.18 25 / 0.25)" }}>
                    <p className="text-[13px] m-0" style={{ color: "var(--bad)" }}>{m.text}</p>
                    {prevUser && prevUser.role === "user" && (
                      <button onClick={() => handleSubmit(prevUser.payload)} disabled={busy}
                        aria-label="Coba lagi"
                        className="mt-2 text-[12px] px-2.5 py-1 rounded-[6px]"
                        style={{ color: "var(--bad)", border: "1px solid oklch(0.58 0.18 25 / 0.35)" }}>
                        Coba lagi
                      </button>
                    )}
                  </div>
                )
              }
              if (m.role === "analyze") return <AnalyzeResultCard key={m.id} title={m.title} result={m.data} />
              return <RecommendationResultCard key={m.id} result={m.data} />
            })
          )}
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--line)", background: "var(--bg-elev)" }}>
        <div className="mx-auto max-w-[860px] px-6 py-3.5">
          <Composer
            mode={mode}
            onModeChange={setMode}
            onSubmit={handleSubmit}
            disabled={busy}
            initialText={initialTitle}
            seedText={seedText}
            onSeedConsumed={() => setSeedText(undefined)}
          />
        </div>
      </div>
    </div>
  )
}

function EmptyState({ onPrefill }: { onPrefill: (mode: Mode, text: string) => void }) {
  return (
    <div>
      <div className="mb-7">
        <h2
          className="text-[22px] font-semibold tracking-tight m-0"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Meja analisis redaksi
        </h2>
        <p className="text-[13px] mt-2 m-0" style={{ color: "var(--fg-muted)" }}>
          Nilai draf sebelum terbit, atau gali data performa untuk tahu apa yang layak ditulis berikutnya.
        </p>
      </div>

      <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
        <CapabilityCard
          icon={<Sparkles size={18} />}
          title="Analisis Artikel"
          desc="16 sinyal editorial, profil kebutuhan pembaca, dan masukan redaksi untuk satu draf."
          example={ANALYZE_EXAMPLE}
          onTryExample={() => onPrefill("analyze", ANALYZE_EXAMPLE)}
        />
        <CapabilityCard
          icon={<BarChart3 size={18} />}
          title="Rekomendasi"
          desc="Temukan artikel berperforma terbaik dan angle berikutnya dari data historis."
          example={RECO_EXAMPLE}
          onTryExample={() => onPrefill("recommendation", RECO_EXAMPLE)}
        />
      </div>
    </div>
  )
}

function CapabilityCard({
  icon,
  title,
  desc,
  example,
  onTryExample,
}: {
  icon: React.ReactNode
  title: string
  desc: string
  example: string
  onTryExample: () => void
}) {
  return (
    <div
      className="rounded-[10px] p-4 flex flex-col gap-3 transition-colors"
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bg-hover)" }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bg-elev)" }}
    >
      <div className="flex items-start gap-3">
        <span
          className="w-8 h-8 rounded-[8px] grid place-items-center shrink-0"
          style={{ background: "var(--accent-soft)", color: "var(--accent-fg)" }}
        >
          {icon}
        </span>
        <div>
          <div className="text-[13.5px] font-semibold leading-snug" style={{ color: "var(--fg)" }}>{title}</div>
          <div className="text-[12px] mt-0.5 leading-snug" style={{ color: "var(--fg-muted)" }}>{desc}</div>
        </div>
      </div>

      <button
        type="button"
        onClick={onTryExample}
        className="text-left w-full rounded-[7px] px-3 py-2"
        style={{ background: "var(--bg-sunken)", border: "1px solid var(--line)" }}
      >
        <div
          className="text-[10.5px] font-medium mb-1"
          style={{ color: "var(--accent-fg)", fontFamily: "var(--font-sans)", letterSpacing: "0.01em" }}
        >
          Coba contoh
        </div>
        <div
          className="text-[11.5px] leading-snug line-clamp-2"
          style={{ color: "var(--fg-muted)", fontStyle: "italic" }}
        >
          {example}
        </div>
      </button>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div
      className="rounded-[12px] p-5"
      style={{ background: "var(--bg-elev)", border: "1px solid var(--line)", boxShadow: "var(--shadow-sm)" }}
    >
      <style>{`
        @keyframes skeletonShimmer {
          0% { opacity: 1; }
          50% { opacity: 0.4; }
          100% { opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          .skeleton-shimmer { animation: none !important; opacity: 0.5; }
        }
      `}</style>
      <div
        className="skeleton-shimmer h-4 rounded-[4px] mb-3 w-2/5"
        style={{ background: "var(--bg-hover)", animation: "skeletonShimmer 1.6s ease-in-out infinite" }}
      />
      <div
        className="skeleton-shimmer h-3 rounded-[4px] mb-2 w-full"
        style={{ background: "var(--bg-sunken)", animation: "skeletonShimmer 1.6s 0.1s ease-in-out infinite" }}
      />
      <div
        className="skeleton-shimmer h-3 rounded-[4px] mb-2 w-4/5"
        style={{ background: "var(--bg-sunken)", animation: "skeletonShimmer 1.6s 0.2s ease-in-out infinite" }}
      />
      <div
        className="skeleton-shimmer h-3 rounded-[4px] w-3/5"
        style={{ background: "var(--bg-sunken)", animation: "skeletonShimmer 1.6s 0.3s ease-in-out infinite" }}
      />
    </div>
  )
}
