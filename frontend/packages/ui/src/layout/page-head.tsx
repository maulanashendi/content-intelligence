import type { ReactNode } from "react"

interface PageHeadProps {
  title: string
  titleDecorator?: string
  subtitle?: string
  action?: ReactNode
  back?: ReactNode
}

export function PageHead({ title, titleDecorator, subtitle, action, back }: PageHeadProps) {
  return (
    <div className="page-head">
      <div>
        {back && <div style={{ marginBottom: 12 }}>{back}</div>}
        <h1 className="page-title">
          {title}
          {titleDecorator && (
            <>
              {" "}
              <span className="serif">{titleDecorator}</span>
            </>
          )}
        </h1>
        {subtitle && <p className="page-sub">{subtitle}</p>}
      </div>
      {action && <div className="page-actions">{action}</div>}
    </div>
  )
}
