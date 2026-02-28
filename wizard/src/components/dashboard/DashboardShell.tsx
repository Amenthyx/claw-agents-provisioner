import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, Bot, Brain, Shield, MessageSquare, Database,
  ScrollText, Settings, Sparkles, ArrowLeft, Bell, Server,
} from 'lucide-react';
import { cn } from '../../lib/cn';

const NAV_ITEMS = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Overview', end: true },
  { to: '/dashboard/agents', icon: Bot, label: 'Agents', end: false },
  { to: '/dashboard/models', icon: Brain, label: 'Models', end: false },
  { to: '/dashboard/security', icon: Shield, label: 'Security', end: false },
  { to: '/dashboard/triggers', icon: Bell, label: 'Triggers', end: false },
  { to: '/dashboard/instances', icon: Server, label: 'Cluster', end: false },
  { to: '/dashboard/data', icon: Database, label: 'Data', end: false },
  { to: '/dashboard/channels', icon: MessageSquare, label: 'Channels', end: false },
  { to: '/dashboard/logs', icon: ScrollText, label: 'Logs', end: false },
  { to: '/dashboard/settings', icon: Settings, label: 'Settings', end: false },
] as const;

export function DashboardShell() {
  return (
    <div className="flex h-screen overflow-hidden bg-surface-0">
      {/* Sidebar */}
      <aside className="flex w-[240px] shrink-0 flex-col border-r border-border-base bg-surface-0">
        <div className="flex items-center gap-2.5 px-5 pt-6 pb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-white">
            <Sparkles size={16} />
          </div>
          <span className="text-base font-semibold tracking-tight text-text-primary">XClaw</span>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-2">
          <ul className="space-y-0.5">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150',
                      isActive
                        ? 'bg-accent/10 text-accent font-medium'
                        : 'text-text-secondary hover:bg-surface-2 hover:text-text-primary',
                    )
                  }
                >
                  <item.icon size={16} />
                  <span>{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="border-t border-border-base px-3 py-3">
          <NavLink
            to="/"
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
          >
            <ArrowLeft size={14} />
            Back to Wizard
          </NavLink>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 py-8">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
