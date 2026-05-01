import type { ArticleMember } from "@ei-fe/api"
import { formatDate, formatScore } from "@ei-fe/core"

interface ArticleRowProps {
  article: ArticleMember
}

export function ArticleRow({ article }: ArticleRowProps) {
  return (
    <tr className="row-clickable">
      <td>
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "var(--fg)", fontWeight: 500 }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)" }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--fg)" }}
        >
          {article.title}
        </a>
        {article.first_paragraph && (
          <p
            style={{
              margin: "4px 0 0",
              fontSize: 12,
              color: "var(--fg-muted)",
              lineHeight: 1.5,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {article.first_paragraph}
          </p>
        )}
      </td>
      <td className="num" style={{ whiteSpace: "nowrap", color: "var(--fg-muted)" }}>
        {article.source_name}
      </td>
      <td className="num" style={{ whiteSpace: "nowrap", color: "var(--fg-faint)" }}>
        {formatDate(article.published_at)}
      </td>
      <td className="num right">{formatScore(article.relevance_score)}</td>
    </tr>
  )
}
