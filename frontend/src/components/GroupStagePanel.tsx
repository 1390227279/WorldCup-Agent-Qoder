import { useEffect, useMemo, useState } from "react";
import type { GroupStageGroup } from "../types";

const GROUPS = "ABCDEFGHIJKL".split("");

const qualificationLabel = {
  GROUP_WINNER: "小组第一",
  RUNNER_UP: "小组第二",
  BEST_THIRD: "最佳第三",
} as const;

export default function GroupStagePanel({ groups }: { groups: Record<string, GroupStageGroup> | null }) {
  const availableGroups = useMemo(
    () => GROUPS.filter((groupName) => groups?.[groupName]),
    [groups],
  );
  const [selectedGroup, setSelectedGroup] = useState("A");

  useEffect(() => {
    if (!availableGroups.includes(selectedGroup) && availableGroups[0]) {
      setSelectedGroup(availableGroups[0]);
    }
  }, [availableGroups, selectedGroup]);

  const group = groups?.[selectedGroup];
  if (!group) {
    return <div className="flex min-h-[520px] items-center justify-center text-sm text-[var(--color-text-muted)]">暂无小组赛模拟数据</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="选择小组">
        {availableGroups.map((groupName) => (
          <button
            key={groupName}
            type="button"
            role="tab"
            aria-selected={selectedGroup === groupName}
            onClick={() => setSelectedGroup(groupName)}
            className={`min-w-12 rounded-md border px-3 py-2 text-sm font-semibold transition-colors ${selectedGroup === groupName
              ? "border-[var(--color-primary)] bg-[var(--color-primary)] text-[#1c1d21]"
              : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]/60 hover:text-white"
            }`}
          >
            {groupName} 组
          </button>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
        <section className="overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="border-b border-[var(--color-border)] px-4 py-3">
            <h2 className="font-semibold text-white">{group.label}积分榜</h2>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">前两名与成绩最好的八个小组第三晋级 32 强</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-[var(--color-surface-raised)] text-xs text-[var(--color-text-muted)]">
                <tr>
                  <th className="px-3 py-2 text-center">排名</th><th className="px-3 py-2 text-left">球队</th>
                  <th className="px-2 py-2">赛</th><th className="px-2 py-2">胜</th><th className="px-2 py-2">平</th><th className="px-2 py-2">负</th>
                  <th className="px-2 py-2">进/失</th><th className="px-2 py-2">净胜</th><th className="px-3 py-2">积分</th><th className="px-3 py-2 text-left">晋级</th>
                </tr>
              </thead>
              <tbody>
                {group.standings.map((row) => (
                  <tr key={row.team_id} className="border-t border-[var(--color-border-muted)]">
                    <td className="px-3 py-3 text-center font-mono text-[var(--color-text-muted)]">{row.position}</td>
                    <td className="px-3 py-3 font-semibold text-white">{row.team.name_cn || row.team.name}<span className="ml-2 text-xs font-normal text-[var(--color-text-muted)]">{row.team.fifa_code}</span></td>
                    <td className="px-2 py-3 text-center">{row.played}</td><td className="px-2 py-3 text-center">{row.wins}</td><td className="px-2 py-3 text-center">{row.draws}</td><td className="px-2 py-3 text-center">{row.losses}</td>
                    <td className="px-2 py-3 text-center font-mono">{row.goals_for}/{row.goals_against}</td>
                    <td className="px-2 py-3 text-center font-mono">{row.goal_difference > 0 ? "+" : ""}{row.goal_difference}</td>
                    <td className="px-3 py-3 text-center font-mono text-base font-bold text-[var(--color-primary)]">{row.points}</td>
                    <td className="px-3 py-3">{row.qualification_type ? <span className={`rounded-full border px-2 py-1 text-xs ${row.qualification_type === "BEST_THIRD" ? "border-[var(--color-secondary)]/60 text-[var(--color-secondary)]" : "border-[var(--color-primary)]/60 text-[var(--color-primary)]"}`}>{qualificationLabel[row.qualification_type]}</span> : <span className="text-xs text-[var(--color-text-muted)]">未晋级</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <h2 className="font-semibold text-white">{group.label}比赛结果</h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
            {[...group.matches].sort((a, b) => a.match_order - b.match_order).map((match) => (
              <div key={match.match_key} className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 rounded-md border border-[var(--color-border-muted)] bg-[var(--color-surface-raised)] px-3 py-3 text-sm">
                <span className="truncate text-right text-white">{match.home_team.name_cn || match.home_team.name}</span>
                <strong className="min-w-16 rounded bg-[#12171b] px-3 py-1 text-center font-mono text-base text-[var(--color-primary)]">{match.home_score} - {match.away_score}</strong>
                <span className="truncate text-white">{match.away_team.name_cn || match.away_team.name}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
