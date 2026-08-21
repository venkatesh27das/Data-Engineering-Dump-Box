import { CircleHelp, FileSpreadsheet, History, Home, MessageSquare, PanelLeftClose, Settings } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { BrandMark } from '../common/BrandMark'

const mainLinks = [
  { to: '/', label: 'Home', icon: Home },
  { to: '/workbooks', label: 'My Workbooks', icon: FileSpreadsheet },
  { to: '/runs', label: 'Run History', icon: History },
]

export function AppShell() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><BrandMark /><span>Workbook Agent</span></div>
        <nav className="main-nav" aria-label="Main navigation">
          {mainLinks.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'}><Icon size={21} /><span>{label}</span></NavLink>
          ))}
        </nav>
        <nav className="utility-nav" aria-label="Utility navigation">
          <NavLink to="/feedback"><MessageSquare size={20} /><span>Feedback</span></NavLink>
          <NavLink to="/settings"><Settings size={20} /><span>Settings</span></NavLink>
        </nav>
        <button className="mobile-close" aria-label="Close navigation"><PanelLeftClose /></button>
      </aside>
      <div className="app-body">
        <header className="topbar"><CircleHelp size={22} /><div className="avatar">AD</div></header>
        <main className="page-container"><Outlet /></main>
      </div>
    </div>
  )
}

