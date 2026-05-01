import { NavLink } from "react-router-dom"

const EDITORIAL_NAV = [
  { to: "/morning", label: "Morning Brief" },
  { to: "/deferred", label: "Ditunda" },
]

const PIPELINE_NAV = [
  { to: "/clustering", label: "Topic Clustering", exact: true },
]

const SOURCES_NAV = [
  { to: "/sources", label: "Content Sources", exact: true },
  { to: "/sources/rss", label: "Input RSS" },
  { to: "/sources/api", label: "Input API" },
  { to: "/sources/schema", label: "Check Schema" },
]

function NavItem({ to, label, exact }: { to: string; label: string; exact?: boolean }) {
  return (
    <NavLink
      to={to}
      end={exact}
      className={({ isActive }: { isActive: boolean }) =>
        isActive ? "nav-item active" : "nav-item"
      }
    >
      {label}
    </NavLink>
  )
}

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">C</div>
        <div>
          <div className="brand-name">Content Intelligence</div>
          <div className="brand-meta">Tempo · Editorial</div>
        </div>
      </div>

      <div className="nav-group">
        <div className="nav-label">Redaksi</div>
        {EDITORIAL_NAV.map(({ to, label }) => (
          <NavItem key={to} to={to} label={label} exact />
        ))}
      </div>

      <div className="nav-group">
        <div className="nav-label">Pipeline</div>
        {PIPELINE_NAV.map(({ to, label, exact }) => (
          <NavItem key={to} to={to} label={label} exact={exact} />
        ))}
      </div>

      <div className="nav-group">
        <div className="nav-label">Sumber Data</div>
        {SOURCES_NAV.map(({ to, label, exact }) => (
          <NavItem key={to} to={to} label={label} exact={exact} />
        ))}
      </div>

      <div className="sidebar-foot">
        <div className="user-chip">
          <div className="avatar">ME</div>
          <div>
            <div className="user-name">Redaksi</div>
            <div className="user-role">Editor</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
