export function UserBubble({ command, text }: { command?: string; text: string }) {
  return (
    <div className="flex justify-end">
      <div className="rounded-[14px_14px_4px_14px] px-3.5 py-2.5 text-[13px] leading-normal max-w-[78%]" style={{ background: "var(--accent)", color: "white" }}>
        {command && (
          <span className="block text-[11px] opacity-70 mb-0.5" style={{ fontFamily: "var(--font-sans)", letterSpacing: "0.01em" }}>
            {command}
          </span>
        )}
        <span className="whitespace-pre-wrap">{text}</span>
      </div>
    </div>
  )
}
