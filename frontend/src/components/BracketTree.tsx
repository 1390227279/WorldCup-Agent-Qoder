import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { BracketStage, Match } from "../types";

const STAGES = ["R32", "R16", "QF", "SF", "FINAL"] as const;
const STAGE_LABELS: Record<string, string> = {
  R32: "32 强",
  R16: "16 强",
  QF: "八强",
  SF: "半决赛",
  FINAL: "决赛",
};

const NODE_W = 170;
const NODE_H = 38;
const COL_GAP = 32;
const ROW_GAP = 1;
const HEADER_H = 34;
const FOOTER_H = 14;
const COL_X = STAGES.map((_, index) => index * (NODE_W + COL_GAP));

function stride(stageIndex: number): number {
  return (NODE_H + ROW_GAP) * 2 ** stageIndex;
}

const TOTAL_H = HEADER_H + stride(0) * 16 + FOOTER_H;

function yCenter(stageIndex: number, matchIndex: number): number {
  const stageStride = stride(stageIndex);
  return HEADER_H + stageStride * matchIndex + stageStride / 2;
}

function matchCount(stageIndex: number): number {
  return 16 >> stageIndex;
}

function matchKey(match: Match): string {
  return match.match_key ?? String(match.id);
}

function teamName(match: Match, side: "home" | "away"): string {
  const team = side === "home" ? match.home_team : match.away_team;
  return team?.name_cn || team?.name || "待定";
}

function compactTeamName(match: Match, side: "home" | "away"): string {
  const name = teamName(match, side);
  return name.length > 7 ? `${name.slice(0, 7)}…` : name;
}

function stageMatches(stages: Record<string, BracketStage> | null, stage: string): Match[] {
  return [...(stages?.[stage]?.matches ?? [])].sort(
    (a, b) => (a.match_order ?? 0) - (b.match_order ?? 0),
  );
}

interface FlatMatch {
  match: Match;
  stageIndex: number;
  matchIndex: number;
}

function buildFlatMatches(stages: Record<string, BracketStage> | null): FlatMatch[] {
  return STAGES.flatMap((stage, stageIndex) => (
    stageMatches(stages, stage)
      .slice(0, matchCount(stageIndex))
      .map((match, matchIndex) => ({ match, stageIndex, matchIndex }))
  ));
}

function CompactMatchCard({
  match,
  selected,
  onClick,
}: {
  match: Match;
  selected: boolean;
  onClick?: (match: Match) => void;
}) {
  const homeWinner = match.winner_team_id === match.home_team?.id;
  const awayWinner = match.winner_team_id === match.away_team?.id;
  return (
    <button
      type="button"
      onClick={() => onClick?.(match)}
      className={`w-full rounded-lg border bg-[var(--color-surface)] p-2 text-left transition-all duration-150 ${selected
        ? "border-[var(--color-primary)] shadow-[var(--shadow-glow)]"
        : "border-[var(--color-border)] hover:border-[var(--color-primary)]/60 hover:bg-[var(--color-surface-raised)]"
      }`}
    >
      <div className={`flex items-center justify-between gap-2 text-sm ${homeWinner ? "font-semibold text-[var(--color-primary)]" : "text-[var(--color-text-muted)]"}`}>
        <span className="truncate">{teamName(match, "home")}</span>
        <span className="font-mono text-white">{match.home_score ?? "—"}</span>
      </div>
      <div className="my-1 h-px bg-[var(--color-border-muted)]" />
      <div className={`flex items-center justify-between gap-2 text-sm ${awayWinner ? "font-semibold text-[var(--color-primary)]" : "text-[var(--color-text-muted)]"}`}>
        <span className="truncate">{teamName(match, "away")}</span>
        <span className="font-mono text-white">{match.away_score ?? "—"}</span>
      </div>
    </button>
  );
}

interface BracketTreeProps {
  stages: Record<string, BracketStage> | null;
  eventInfluenced?: boolean;
  selectedMatchKey?: string | null;
  onMatchClick?: (match: Match) => void;
}

export default function BracketTree({ stages, eventInfluenced, selectedMatchKey, onMatchClick }: BracketTreeProps) {
  const [stageIndex, setStageIndex] = useState(0);
  const flatMatches = useMemo(() => buildFlatMatches(stages), [stages]);
  const matchesByKey = useMemo(
    () => new Map(flatMatches.map((item) => [matchKey(item.match), item])),
    [flatMatches],
  );
  const highlightedKeys = useMemo(() => {
    const result = new Set<string>();
    if (!selectedMatchKey || !matchesByKey.has(selectedMatchKey)) return result;
    const visitBackward = (key: string) => {
      if (result.has(key)) return;
      result.add(key);
      const item = matchesByKey.get(key);
      for (const source of item?.match.source_slots ?? []) {
        if (matchesByKey.has(source)) visitBackward(source);
      }
    };
    visitBackward(selectedMatchKey);
    let current = selectedMatchKey;
    while (true) {
      const next = flatMatches.find((item) => item.match.source_slots?.includes(current));
      if (!next) break;
      current = matchKey(next.match);
      result.add(current);
    }
    return result;
  }, [flatMatches, matchesByKey, selectedMatchKey]);

  if (flatMatches.length === 0) {
    return (
      <div className="flex min-h-[420px] items-center justify-center text-center">
        <div>
          <div className="mx-auto mb-3 h-8 w-8 animate-pulse rounded-md border border-[var(--color-primary)] bg-[var(--color-primary)]/10" />
          <p className="text-sm text-[var(--color-text-muted)]">正在加载淘汰赛路径</p>
        </div>
      </div>
    );
  }

  const svgWidth = COL_X[COL_X.length - 1] + NODE_W + 8;

  return (
    <div className="min-w-0">
      <div className="mb-3 flex items-center justify-between gap-3 border-b border-[var(--color-border)] pb-3">
        <div>
          <p className="dashboard-label uppercase">代表路径</p>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">{eventInfluenced ? "当前事件情景" : "基础实力基线"} · 点击比赛查看数学结果与 AI 解读</p>
        </div>
        <div className="hidden items-center gap-4 text-[11px] text-[var(--color-text-muted)] sm:flex">
          <span className="flex items-center gap-1.5"><i className="h-0.5 w-5 bg-[var(--color-border)]" />默认路径</span>
          <span className="flex items-center gap-1.5"><i className="h-0.5 w-5 bg-[var(--color-primary)] shadow-[var(--shadow-glow)]" />当前链路</span>
        </div>
      </div>

      <div className="hidden lg:block" style={{ height: "clamp(560px, calc(100vh - 285px), 720px)" }}>
        <svg width="100%" height="100%" viewBox={`0 0 ${svgWidth} ${TOTAL_H}`} preserveAspectRatio="xMidYMid meet" className="block overflow-visible">
          {STAGES.map((stage, index) => (
            <text key={stage} x={COL_X[index] + NODE_W / 2} y={18} textAnchor="middle" fill="var(--color-text-muted)" fontSize={13} fontWeight={600} letterSpacing="0.05em">
              {STAGE_LABELS[stage]}
            </text>
          ))}

          {flatMatches.flatMap((target) => {
            if (target.stageIndex === 0) return [];
            const targetKey = matchKey(target.match);
            return (target.match.source_slots ?? []).flatMap((source) => {
              const feeder = matchesByKey.get(source);
              if (!feeder) return [];
              const sourceKey = matchKey(feeder.match);
              const active = highlightedKeys.has(sourceKey) && highlightedKeys.has(targetKey);
              const leftX = COL_X[feeder.stageIndex] + NODE_W;
              const rightX = COL_X[target.stageIndex];
              const middleX = rightX - COL_GAP / 2;
              const leftY = yCenter(feeder.stageIndex, feeder.matchIndex);
              const rightY = yCenter(target.stageIndex, target.matchIndex);
              return [(
                <motion.path
                  key={`${sourceKey}-${targetKey}`}
                  d={`M${leftX},${leftY} H${middleX} V${rightY} H${rightX}`}
                  fill="none"
                  stroke={active ? "var(--color-primary)" : "var(--color-border)"}
                  strokeWidth={active ? 2.4 : 2}
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: active ? 1 : 0.78 }}
                  transition={{ duration: 0.45, ease: "easeOut" }}
                  style={active ? { filter: "drop-shadow(0 0 4px rgba(230,183,16,0.4))" } : undefined}
                />
              )];
            });
          })}

          {flatMatches.map(({ match, stageIndex: currentStageIndex, matchIndex }) => {
            const key = matchKey(match);
            const selected = key === selectedMatchKey;
            const highlighted = highlightedKeys.has(key);
            const x = COL_X[currentStageIndex];
            const y = yCenter(currentStageIndex, matchIndex) - NODE_H / 2;
            const homeWinner = match.winner_team_id === match.home_team?.id;
            const awayWinner = match.winner_team_id === match.away_team?.id;
            return (
              <motion.g
                key={key}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: highlightedKeys.size > 0 && !highlighted ? 0.42 : 1, x: 0 }}
                transition={{ duration: 0.2 }}
                onClick={() => onMatchClick?.(match)}
                className="cursor-pointer"
              >
                <rect x={x} y={y} width={NODE_W} height={NODE_H} rx={8} fill={selected ? "var(--color-surface-raised)" : "var(--color-surface)"} stroke={selected || highlighted ? "var(--color-primary)" : "var(--color-border)"} strokeWidth={selected ? 2.4 : highlighted ? 1.8 : 1.4} style={selected || highlighted ? { filter: "drop-shadow(0 0 5px rgba(230,183,16,0.28))" } : undefined} />
                <line x1={x + 8} y1={y + NODE_H / 2} x2={x + NODE_W - 8} y2={y + NODE_H / 2} stroke="var(--color-border-muted)" />
                <text x={x + 9} y={y + 13.5} fill={homeWinner ? "var(--color-primary)" : "var(--color-text-muted)"} fontSize={12} fontWeight={homeWinner ? 600 : 400}>{compactTeamName(match, "home")}</text>
                <text x={x + NODE_W - 9} y={y + 13.5} textAnchor="end" fill="white" fontFamily="monospace" fontSize={12} fontWeight={600}>{match.home_score ?? "—"}</text>
                <text x={x + 9} y={y + 33} fill={awayWinner ? "var(--color-primary)" : "var(--color-text-muted)"} fontSize={12} fontWeight={awayWinner ? 600 : 400}>{compactTeamName(match, "away")}</text>
                <text x={x + NODE_W - 9} y={y + 33} textAnchor="end" fill="white" fontFamily="monospace" fontSize={12} fontWeight={600}>{match.away_score ?? "—"}</text>
              </motion.g>
            );
          })}
        </svg>
      </div>

      <div className="lg:hidden">
        <div className="mb-4 flex gap-1 overflow-x-auto border-b border-[var(--color-border)] pb-2">
          {STAGES.map((stage, index) => (
            <button key={stage} type="button" onClick={() => setStageIndex(index)} className={`shrink-0 rounded-md border px-3 py-1.5 text-xs transition-colors ${stageIndex === index ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]" : "border-transparent text-[var(--color-text-muted)] hover:border-[var(--color-border)]"}`}>
              {STAGE_LABELS[stage]}
            </button>
          ))}
        </div>

        <div className="hidden gap-4 md:grid md:grid-cols-2">
          {[stageIndex, Math.min(stageIndex + 1, STAGES.length - 1)].filter((value, index, list) => list.indexOf(value) === index).map((index) => {
            const stage = STAGES[index];
            return (
              <section key={stage} className="min-w-0">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="font-semibold">{STAGE_LABELS[stage]}</h3>
                  <span className="text-xs text-[var(--color-text-muted)]">{stageMatches(stages, stage).length} 场</span>
                </div>
                <div className="space-y-2">
                  {stageMatches(stages, stage).map((match) => <CompactMatchCard key={matchKey(match)} match={match} selected={matchKey(match) === selectedMatchKey} onClick={onMatchClick} />)}
                </div>
              </section>
            );
          })}
        </div>

        <div className="space-y-2 md:hidden">
          {stageMatches(stages, STAGES[stageIndex]).map((match) => <CompactMatchCard key={matchKey(match)} match={match} selected={matchKey(match) === selectedMatchKey} onClick={onMatchClick} />)}
        </div>
      </div>
    </div>
  );
}
