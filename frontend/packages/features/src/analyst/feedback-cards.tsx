import type { EditorialFeedback } from "@ei-fe/api"

type Tone = "judul" | "info" | "bias" | "angle"
const STYLES: Record<Tone, { bg: string; border: string; head: string; dot: string }> = {
  judul: { bg: "var(--accent-soft)", border: "oklch(0.55 0.15 262 / 0.25)", head: "var(--accent-fg)", dot: "var(--accent)" },
  info:  { bg: "var(--warn-soft)",   border: "oklch(0.72 0.15 75 / 0.3)",   head: "oklch(0.45 0.13 75)", dot: "var(--warn)" },
  bias:  { bg: "var(--bad-soft)",    border: "oklch(0.58 0.18 25 / 0.25)",  head: "var(--bad)", dot: "var(--bad)" },
  angle: { bg: "var(--info-soft)",   border: "oklch(0.60 0.12 230 / 0.25)", head: "oklch(0.42 0.13 230)", dot: "var(--info)" },
}

function Card({ tone, title, items }: { tone: Tone; title: string; items: string[] }) {
  if (!items || items.length === 0) return null
  const s = STYLES[tone]
  return (
    <div
      className="rounded-[var(--radius)] p-3"
      style={{ background: s.bg, border: `1px solid ${s.border}` }}
    >
      <p
        className="text-[10.5px] font-semibold tracking-[0.04em] mb-1.5"
        style={{ color: s.head }}
      >
        {title}
      </p>
      <ul className="flex flex-col gap-1.5 m-0 p-0 list-none">
        {items.map((it, i) => (
          <li key={i} className="text-[12px] leading-snug pl-3 relative" style={{ color: "var(--fg-muted)" }}>
            <span className="absolute left-0.5 top-[7px] w-1 h-1 rounded-full" style={{ background: s.dot }} />
            {it}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function FeedbackCards({ feedback }: { feedback: EditorialFeedback }) {
  return (
    <div
      className="grid gap-3 max-[560px]:[grid-template-columns:1fr]"
      style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}
    >
      <Card tone="judul" title="Saran judul" items={feedback.recommendation_judul} />
      <Card tone="info" title="Informasi kurang" items={feedback.missing_info} />
      <Card tone="bias" title="Cek bias" items={feedback.bias_check} />
      <Card tone="angle" title="Angle lanjutan" items={feedback.next_angle} />
    </div>
  )
}
