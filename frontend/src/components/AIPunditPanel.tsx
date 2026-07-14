import { motion } from "framer-motion";
import type {
  Match,
  MatchMathContext,
  MatchPredictionResponse,
  ReasoningStep,
} from "../types";

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2 mt-5 flex items-center gap-2 first:mt-0">
      <span className="text-xs font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
        {children}
      </span>
      <div className="h-px flex-1 bg-[var(--color-text-muted)] opacity-15" />
    </div>
  );
}

function teamName(team: Match["home_team"]): string {
  return team?.name_cn || team?.name || "待定";
}

function winnerName(match: Match, math?: MatchMathContext): string {
  const winnerTeamId = math?.winner_team_id ?? match.winner_team_id;
  if (winnerTeamId === match.home_team?.id) return teamName(match.home_team);
  if (winnerTeamId === match.away_team?.id) return teamName(match.away_team);
  return math?.winner || match.winner || "待定";
}

function percentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function MathSummary({ match, math }: { match: Match; math?: MatchMathContext }) {
  const score = math?.predicted_score
    ?? (match.home_score != null && match.away_score != null
      ? `${match.home_score}-${match.away_score}`
      : "暂无比分");

  return (
    <div className="rounded-lg border border-[var(--color-primary)]/40 bg-[var(--color-bg)] p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-[var(--color-primary)]">数学模型结果</span>
        <span className="text-[10px] text-[var(--color-text-muted)]">
          后端模拟结果 · AI 不可修改
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-[var(--color-text-muted)]">代表路径比分</p>
          <p className="font-mono text-2xl font-bold text-[var(--color-accent)]">{score}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--color-text-muted)]">晋级球队</p>
          <p className="text-lg font-bold">{winnerName(match, math)}</p>
          <p className="text-[10px] text-[var(--color-text-muted)]">
            {math?.decided_by === "PENALTIES" ? "点球决胜" : "常规时间"}
          </p>
        </div>
      </div>

      {math && (
        <>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-lg bg-[var(--color-surface)] p-2">
              <p className="text-[var(--color-text-muted)]">主胜</p>
              <p className="mt-1 font-bold">{percentage(math.probabilities.home_win)}</p>
            </div>
            <div className="rounded-lg bg-[var(--color-surface)] p-2">
              <p className="text-[var(--color-text-muted)]">平局</p>
              <p className="mt-1 font-bold">{percentage(math.probabilities.draw)}</p>
            </div>
            <div className="rounded-lg bg-[var(--color-surface)] p-2">
              <p className="text-[var(--color-text-muted)]">客胜</p>
              <p className="mt-1 font-bold">{percentage(math.probabilities.away_win)}</p>
            </div>
          </div>
          <div className="mt-3 flex justify-between text-xs text-[var(--color-text-muted)]">
            <span>{teamName(math.home_team)} λ {math.home_lambda.toFixed(2)}</span>
            <span>{teamName(math.away_team)} λ {math.away_lambda.toFixed(2)}</span>
          </div>
          {math.math_events.length > 0 && (
            <div className="mt-3 rounded-lg bg-[var(--color-gold)]/10 p-2 text-xs">
              <p className="mb-1 font-semibold text-[var(--color-gold)]">本场数学影响事件</p>
              {math.math_events.map((event) => (
                <p key={event.event_id} className="text-[var(--color-text-muted)]">
                  · {event.title}
                </p>
              ))}
            </div>
          )}
          {math.narrative_events.length > 0 && (
            <div className="mt-3 rounded-lg border border-dashed border-[var(--color-border)] bg-transparent p-2 text-xs">
              <p className="mb-1 font-semibold">本场 AI 解读背景</p>
              {math.narrative_events.map((event) => (
                <p key={event.event_id} className="text-[var(--color-text-muted)]">
                  · {event.title}（不影响数学胜率）
                </p>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ReasoningChain({ chain }: { chain: ReasoningStep[] }) {
  return (
    <div className="space-y-3">
      {chain.map((step, index) => (
        <motion.div
          key={`${step.step_number}-${index}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.06 }}
          className="border-l-2 border-[var(--color-primary)] pl-3"
        >
          <p className="text-xs font-bold text-[var(--color-primary)]">
            步骤 {index + 1}
          </p>
          {step.finding && <p className="mt-1 text-sm">{step.finding}</p>}
          {step.analysis && (
            <p className="mt-1 text-xs leading-relaxed text-[var(--color-text-muted)]">
              {step.analysis}
            </p>
          )}
        </motion.div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text-muted)]">AI</span>
      <p className="text-sm text-[var(--color-text-muted)]">暂无 AI 战术解读</p>
      <p className="mt-1 text-xs text-[var(--color-text-muted)] opacity-60">
        选择一场比赛后，先展示数学结果，再生成解释报告
      </p>
    </div>
  );
}

interface Props {
  match: Match | null;
  analysis: MatchPredictionResponse | null;
  isLoading?: boolean;
}

export default function AIPunditPanel({ match, analysis, isLoading = false }: Props) {
  if (!match) {
    return <EmptyState />;
  }

  const agent = analysis?.agent;
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <MathSummary match={match} math={analysis?.math} />

      <SectionTitle>AI 战术解读</SectionTitle>
      {isLoading && (
        <motion.div
          animate={{ opacity: [0.45, 1, 0.45] }}
          transition={{ repeat: Infinity, duration: 1.5 }}
          className="rounded-lg bg-[var(--color-bg)] p-4 text-center text-sm text-[var(--color-text-muted)]"
        >
          正在基于上述数学结果生成中文解释…
        </motion.div>
      )}

      {!isLoading && agent?.status === "agent_unavailable" && (
        <div className="rounded-lg border border-[var(--color-gold)]/30 bg-[var(--color-gold)]/10 p-3 text-xs text-[var(--color-gold)]">
          ⚠️ {agent.message || "AI 暂时不可用；上方数学结果不受影响。"}
        </div>
      )}

      {!isLoading && agent?.status === "available" && (
        <>
          <div className="space-y-2">
            {agent.key_factors.map((factor, index) => (
              <p key={index} className="text-sm leading-relaxed">
                <span className="mr-2 text-[var(--color-primary)]">{index + 1}.</span>{factor}
              </p>
            ))}
          </div>
          {agent.risk_notes.length > 0 && (
            <>
              <SectionTitle>风险与边界</SectionTitle>
              <div className="space-y-1 text-xs text-[var(--color-text-muted)]">
                {agent.risk_notes.map((note, index) => <p key={index}>· {note}</p>)}
              </div>
            </>
          )}
          {agent.reasoning_chain.length > 0 && (
            <>
              <SectionTitle>解释步骤</SectionTitle>
              <ReasoningChain chain={agent.reasoning_chain} />
            </>
          )}
        </>
      )}
    </motion.div>
  );
}
