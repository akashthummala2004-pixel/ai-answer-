import { useState, type ReactNode } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { ClipboardCheck, History, LayoutDashboard, LogOut, Menu, Moon, PlusCircle, Radio, Settings, Sun, WifiOff, X } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../lib/theme';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/verify', label: 'New Verification', icon: PlusCircle },
  { to: '/history', label: 'History', icon: History },
  { to: '/review', label: 'Review Queue', icon: ClipboardCheck },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white p-1 shadow-sm ring-1 ring-ink-200 dark:ring-ink-700">
        <img src="/mindmasters-mark.png" alt="Mind Masters AI Solutions" className="h-full w-full object-contain" />
      </div>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-ink-900 dark:text-white">Answer Verification</p>
        <p className="text-[11px] font-medium uppercase tracking-wider text-ink-500 dark:text-ink-400">Mind Masters AI</p>
      </div>
    </div>
  );
}

function ModeIndicator() {
  const { health } = useApp();
  if (!health) return null;
  const live = health.ai_mode === 'live';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${
        live
          ? 'bg-brand-50 text-brand-700 ring-brand-200 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/30'
          : 'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30'
      }`}
      title={live ? `AI analysis available (${health.default_model})` : 'AI analysis is unavailable: OpenRouter is not configured'}
    >
      {live ? <Radio className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
      {live ? 'AI online' : 'AI unavailable'}
    </span>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { session, signOut, health } = useApp();
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 py-5">
        <Logo />
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                isActive
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                  : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900 dark:text-ink-400 dark:hover:bg-ink-800 dark:hover:text-white'
              }`
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-ink-200 p-4 dark:border-ink-800">
        {health?.auth_required && session ? (
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-xs text-ink-500 dark:text-ink-400" title={session.email ?? ''}>{session.email}</p>
            <button onClick={signOut} className="rounded-md p-1.5 text-ink-500 hover:bg-ink-100 hover:text-ink-900 dark:hover:bg-ink-800 dark:hover:text-white" title="Sign out">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <p className="text-xs text-ink-500 dark:text-ink-400">Local mode · authentication disabled</p>
        )}
        <p className="mt-2 text-[11px] text-ink-400 dark:text-ink-500">© Mind Masters AI Solutions Pvt. Ltd.</p>
      </div>
    </div>
  );
}

export function AppShell({ banner }: { banner?: ReactNode }) {
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const current = NAV.find((n) => (n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)));

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-ink-200 bg-white lg:block dark:border-ink-800 dark:bg-ink-900">
        <SidebarContent />
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink-950/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-white shadow-xl dark:bg-ink-900">
            <button className="absolute right-3 top-5 rounded-md p-1.5 text-ink-500" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b border-ink-200 bg-white/80 px-4 backdrop-blur sm:px-6 dark:border-ink-800 dark:bg-ink-950/80">
          <div className="flex items-center gap-3">
            <button className="rounded-md p-1.5 text-ink-600 lg:hidden dark:text-ink-300" onClick={() => setOpen(true)} aria-label="Open menu">
              <Menu className="h-5 w-5" />
            </button>
            <p className="text-sm font-medium text-ink-500 dark:text-ink-400">{current?.label ?? 'Verification'}</p>
          </div>
          <div className="flex items-center gap-3">
            <ModeIndicator />
            <button
              onClick={toggle}
              className="rounded-lg p-2 text-ink-500 transition hover:bg-ink-100 hover:text-ink-900 dark:text-ink-400 dark:hover:bg-ink-800 dark:hover:text-white"
              aria-label="Toggle theme"
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          {banner}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
