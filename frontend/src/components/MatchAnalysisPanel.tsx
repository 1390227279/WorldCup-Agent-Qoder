import AIPunditPanel from "./AIPunditPanel";
import type { Match, MatchPredictionResponse } from "../types";

interface Props {
  match: Match | null;
  analysis: MatchPredictionResponse | null;
  isLoading?: boolean;
  error?: Error | null;
  onClose?: () => void;
}

function teamName(match: Match, side: "home" | "away"): string {
  const team = side === "home" ? match.home_team : match.away_team;
  return team?.name_cn || team?.name || "待定";
}

export default function MatchAnalysisPanel({ match, analysis, isLoading = false, error, onClose }: Props) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-[var(--color-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
        <div>
          <p className="dashboard-label uppercase">AI 战情面板</p>
          <p className="mt-1 text-sm font-semibold">{match ? match.round_name ?? match.stage : "等待选择比赛"}</p>
        </div>
        {onClose && (
          <button type="button" onClick={onClose} className="rounded-md border border-[var(--color-border)] px-2.5 py-1.5 text-xs text-[var(--color-text-muted)] transition-colors hover:text-white">关闭</button>
        )}
      </div>

      {match && (
        <div className="border-b border-[var(--color-border)] px-5 py-4">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <p className="truncate text-right font-semibold">{teamName(match, "home")}</p>
            <div className="rounded-md border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/10 px-3 py-2 font-mono text-xl font-semibold text-[var(--color-primary)]">
              {match.home_score ?? "—"} : {match.away_score ?? "—"}
            </div>
            <p className="truncate font-semibold">{teamName(match, "away")}</p>
          </div>
          <p className="mt-2 text-center text-[11px] text-[var(--color-text-muted)]">比赛编号 {match.match_key ?? match.id}</p>
        </div>
      )}

      {error && (
        <div className="mx-5 mt-4 rounded-md border border-[var(--color-error)]/30 bg-[var(--color-error)]/10 p-3 text-xs text-[var(--color-error)]">
          智能解释请求失败：{error.message}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <AIPunditPanel match={match} analysis={analysis} isLoading={isLoading} />
      </div>
    </div>
  );
}
