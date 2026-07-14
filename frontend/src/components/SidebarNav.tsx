import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8">
      <path d="M3.5 10.5 12 3.8l8.5 6.7v9.2H14v-5.8h-4v5.8H3.5z" />
    </svg>
  );
}

function BracketIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8">
      <path d="M4 4h5v5H4zM4 15h5v5H4zM15 9.5h5v5h-5zM9 6.5h3v5.5h3M9 17.5h3V12" />
    </svg>
  );
}

function EventsIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8">
      <path d="M6 3.8h12v16.4H6zM9 8h6M9 12h6M9 16h4" />
    </svg>
  );
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "预测总览", icon: <HomeIcon /> },
  { to: "/bracket", label: "淘汰赛推演", icon: <BracketIcon /> },
  { to: "/admin/events", label: "赛事事件", icon: <EventsIcon /> },
];

function navClassName({ isActive }: { isActive: boolean }) {
  return `group relative flex h-11 w-full items-center gap-3 rounded-lg border px-3 transition-all duration-150 ${isActive
    ? "border-[var(--color-accent)]/40 bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
    : "border-transparent text-[var(--color-text-muted)] hover:border-[var(--color-border)] hover:bg-[var(--color-surface-raised)] hover:text-white"
  }`;
}

function mobileNavClassName({ isActive }: { isActive: boolean }) {
  return `flex h-10 w-10 items-center justify-center rounded-lg border transition-all duration-150 ${isActive
    ? "border-[var(--color-accent)]/40 bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
    : "border-transparent text-[var(--color-text-muted)] hover:border-[var(--color-border)] hover:text-white"
  }`;
}

export default function SidebarNav() {
  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-44 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-4 lg:flex">
        <NavLink to="/" className="mb-6 border-b border-[var(--color-border)] px-2 pb-5">
          <p className="text-sm font-semibold text-[var(--color-primary)]">世界杯预测</p>
          <p className="mt-1 text-[10px] tracking-wider text-[var(--color-text-muted)]">赛事推演指挥中心</p>
        </NavLink>
        <nav aria-label="主导航" className="flex flex-1 flex-col gap-2">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"} aria-label={item.label} className={navClassName}>
              {item.icon}
              <span className="text-sm font-medium">{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-2 border-t border-[var(--color-border)] px-2 pt-4 text-xs text-[var(--color-text-muted)]">
          <span className="h-2 w-2 rounded-full bg-[var(--color-secondary)] shadow-[0_0_8px_rgba(74,222,128,0.55)]" />
          系统在线
        </div>
      </aside>

      <nav aria-label="移动端主导航" className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)]/95 px-3 backdrop-blur-md lg:hidden">
        <NavLink to="/" className="text-sm font-semibold text-[var(--color-primary)]">
          世界杯推演中心
        </NavLink>
        <div className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"} aria-label={item.label} className={mobileNavClassName}>
              {item.icon}
            </NavLink>
          ))}
        </div>
      </nav>
    </>
  );
}
