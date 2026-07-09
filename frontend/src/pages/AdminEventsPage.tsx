import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Event } from "../types";

export default function AdminEventsPage() {
  const { data: events, isLoading } = useQuery({
    queryKey: ["events"],
    queryFn: api.getEvents,
  });

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <Link
        to="/"
        className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors mb-8 inline-block"
      >
        ← 返回首页
      </Link>

      <header className="mb-8">
        <h1 className="text-3xl font-bold mb-2">📋 事件管理面板</h1>
        <p className="text-[var(--color-text-muted)]">
          动态事件注入 · Agent 实时感知 · 自适应权重调整
        </p>
      </header>

      {isLoading ? (
        <p className="text-[var(--color-text-muted)]">加载中...</p>
      ) : (
        <div className="space-y-3">
          {Array.isArray(events) &&
            events.map((event: Event) => (
              <div
                key={event.id}
                className="bg-[var(--color-surface)] rounded-lg p-4 border-l-4"
                style={{
                  borderLeftColor:
                    event.severity === "CRITICAL"
                      ? "#e94560"
                      : event.severity === "MAJOR"
                        ? "#f59e0b"
                        : "#3b82f6",
                }}
              >
                <div className="flex justify-between items-start mb-1">
                  <div>
                    <span className="text-xs text-[var(--color-text-muted)] uppercase mr-2">
                      [{event.type}]
                    </span>
                    <span className="font-semibold">{event.title}</span>
                  </div>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={{
                      background:
                        event.severity === "CRITICAL"
                          ? "rgba(233,69,96,0.2)"
                          : event.severity === "MAJOR"
                            ? "rgba(245,158,11,0.2)"
                            : "rgba(59,130,246,0.2)",
                    }}
                  >
                    {event.severity}
                  </span>
                </div>
                {event.description && (
                  <p className="text-sm text-[var(--color-text-muted)] mb-1">
                    {event.description}
                  </p>
                )}
                {event.impact && (
                  <p className="text-xs text-[var(--color-text-muted)]">
                    影响: {JSON.stringify(event.impact)}
                  </p>
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
