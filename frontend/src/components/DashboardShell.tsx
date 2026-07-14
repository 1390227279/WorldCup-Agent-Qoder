import type { ReactNode } from "react";
import SidebarNav from "./SidebarNav";

export default function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      <SidebarNav />
      <div className="min-w-0 lg:pl-16">
        <main className="min-h-screen min-w-0">{children}</main>
      </div>
    </div>
  );
}
