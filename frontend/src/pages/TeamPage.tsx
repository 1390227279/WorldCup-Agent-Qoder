import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import type { Team, Event } from "../types";

export default function TeamPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["team", id],
    queryFn: () => api.getTeam(Number(id)),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 text-center">
        <p className="text-[var(--color-text-muted)]">加载中...</p>
      </div>
    );
  }

  const team = data as (Team & { events?: Event[] }) | undefined;
  if (!team) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 text-center">
        <p className="text-[var(--color-text-muted)]">球队不存在</p>
        <Link to="/" className="text-[var(--color-primary)] mt-4 inline-block">
          返回首页
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <Link
        to="/"
        className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors mb-8 inline-block"
      >
        ← 返回首页
      </Link>

      <div className="bg-[var(--color-surface)] rounded-xl p-8 mb-8">
        <h1 className="text-3xl font-bold mb-2">{team.name_cn}</h1>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="FIFA 排名" value={team.fifa_ranking?.toString() ?? "-"} />
          <Stat label="ELO 评分" value={team.elo_rating?.toFixed(0) ?? "-"} />
          <Stat
            label="世界杯冠军"
            value={team.stats?.world_cup_titles?.toString() ?? "0"}
          />
          <Stat
            label="参赛次数"
            value={team.stats?.appearances?.toString() ?? "-"}
          />
        </div>

        <div className="mt-4 text-[var(--color-text-muted)] text-sm">
          <p>
            赛事：{team.tournament?.name_cn ?? "未关联赛事"} · 小组：{team.tournament?.group_name ?? "待定"} · 第 {team.tournament?.pot ?? "-"} 档
          </p>
          <p>历史最佳成绩：{team.stats?.world_cup_titles ? `${team.stats.world_cup_titles} 次夺冠` : "尚未夺冠"}</p>
        </div>
      </div>

      {/* Active Events */}
      {team.events && team.events.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">⚡ 活跃事件</h2>
          <div className="space-y-3">
            {team.events.map((event) => (
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
                  <span className="font-semibold">{event.title}</span>
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
                    {event.severity === "CRITICAL" ? "严重" : event.severity === "MAJOR" ? "重要" : "一般"}
                  </span>
                </div>
                {event.description && (
                  <p className="text-sm text-[var(--color-text-muted)]">
                    {event.description}
                  </p>
                )}
                {event.source && (
                  <p className="text-xs text-[var(--color-text-muted)] mt-2">
                    来源: {event.source}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-2xl font-bold text-[var(--color-gold)]">{value}</div>
      <div className="text-xs text-[var(--color-text-muted)] mt-1">{label}</div>
    </div>
  );
}
