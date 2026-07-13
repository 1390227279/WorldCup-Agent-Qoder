import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type {
  Match,
  BracketStage,
} from "../types";

const STAGES = ["R32", "R16", "QF", "SF", "FINAL"] as const;

const STAGE_LABELS: Record<string, string> = {
  R32: "32 强",
  R16: "16 强",
  QF: "1/4 决赛",
  SF: "半决赛",
  FINAL: "决赛",
};

const NODE_W = 176;
const NODE_H = 38;
const COL_GAP = 42;
const MIN_GAP_Y = 2;
const HEADER_H = 34;
const FOOTER_H = 28;
const COL_X = STAGES.map((_, i) => i * (NODE_W + COL_GAP));

function flagEmoji(code: string | undefined | null): string {
  if (!code || code.length < 2) return "🏳️";
  return code
    .toUpperCase()
    .slice(0, 2)
    .split("")
    .map((c) => String.fromCodePoint(0x1f1e6 + c.charCodeAt(0) - 65))
    .join("");
}

function stride(stageIdx: number): number {
  return (NODE_H + MIN_GAP_Y) * Math.pow(2, stageIdx);
}

const TOTAL_H = HEADER_H + stride(0) * 16 + FOOTER_H;

function yCenter(stageIdx: number, matchIdx: number): number {
  const s = stride(stageIdx);
  return HEADER_H + s * matchIdx + s / 2;
}

function matchCount(stageIdx: number): number {
  return 16 >> stageIdx;
}

interface FlatMatch {
  match: Match;
  stageIdx: number;
  matchIdx: number;
}

function buildFlatMatches(
  stages: Record<string, BracketStage> | null,
): FlatMatch[] {
  const stageOrder = ["R32", "R16", "QF", "SF", "FINAL"];
  const result: FlatMatch[] = [];
  if (!stages) return result;
  stageOrder.forEach((stageName, stageIdx) => {
    const matches = [...(stages[stageName]?.matches ?? [])]
      .sort((a, b) => (a.match_order ?? 0) - (b.match_order ?? 0));
    matches.slice(0, matchCount(stageIdx)).forEach((match, matchIdx) => {
      result.push({
        match,
        stageIdx,
        matchIdx,
      });
    });
  });
  return result;
}

function MatchDetailCard({ flatMatch, svgWidth }: { flatMatch: FlatMatch; svgWidth: number }) {
  const { match } = flatMatch;
  const winnerTeam = match.winner_team_id === match.home_team?.id
    ? match.home_team
    : match.winner_team_id === match.away_team?.id
      ? match.away_team
      : null;
  const winnerName = winnerTeam?.name_cn || winnerTeam?.name || match.winner || "-";
  const x = COL_X[flatMatch.stageIdx];
  const y = yCenter(flatMatch.stageIdx, flatMatch.matchIdx);
  const popLeft = x + NODE_W + 12 > svgWidth - 260 ? x - 260 : x + NODE_W + 12;
  const popTop = Math.max(8, Math.min(y - 80, TOTAL_H - 260));
  return (
    <foreignObject x={popLeft} y={popTop} width={250} height={250}>
      <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-primary)", borderRadius: 12, padding: 14, fontSize: 12, color: "var(--color-text)", boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }}>
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>{STAGE_LABELS[match.stage] ?? match.stage}</div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span>{flagEmoji(match.home_team?.fifa_code)} {match.home_team?.name_cn ?? match.home_team?.name ?? "TBD"}</span>
          <span style={{ fontWeight: 700 }}>{match.home_score ?? "-"}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
          <span>{flagEmoji(match.away_team?.fifa_code)} {match.away_team?.name_cn ?? match.away_team?.name ?? "TBD"}</span>
          <span style={{ fontWeight: 700 }}>{match.away_score ?? "-"}</span>
        </div>
        <div style={{ borderTop: "1px solid #333", paddingTop: 8, marginBottom: 6 }}>
          <span style={{ color: "var(--color-text-muted)" }}>📊 数学模型代表路径</span>
        </div>
        <div style={{ color: "var(--color-text-muted)", fontSize: 11, marginBottom: 4 }}>
          获胜方：<strong style={{ color: "var(--color-text)" }}>{winnerName}</strong>
        </div>
        <div style={{ color: "var(--color-text-muted)", fontSize: 11, marginBottom: 4 }}>
          决胜方式：{match.decided_by === "PENALTIES" ? "点球决胜" : "常规时间"}
        </div>
        <div style={{ color: "var(--color-text-muted)", fontSize: 10 }}>
          比赛编号：{match.match_key ?? match.id}
        </div>
      </div>
    </foreignObject>
  );
}

interface BracketTreeProps {
  stages: Record<string, BracketStage> | null;
  eventInfluenced?: boolean;
  onMatchClick?: (match: Match) => void;
}

export default function BracketTree({ stages, eventInfluenced, onMatchClick }: BracketTreeProps) {
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const flatMatches = useMemo(
    () => buildFlatMatches(stages),
    [stages],
  );
  const matchesByKey = useMemo(
    () => new Map(
      flatMatches
        .filter((flatMatch) => flatMatch.match.match_key)
        .map((flatMatch) => [flatMatch.match.match_key as string, flatMatch]),
    ),
    [flatMatches],
  );
  const svgW = COL_X[COL_X.length - 1] + NODE_W + 16;
  const svgH = TOTAL_H;
  const hoveredFlat = hoveredKey != null
    ? flatMatches.find((flatMatch) => (
      (flatMatch.match.match_key ?? String(flatMatch.match.id)) === hoveredKey
    ))
    : null;
  const hasData = flatMatches.length > 0;

  if (!hasData) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 400 }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>⚽</div>
          <p style={{ color: "var(--color-text-muted)", fontSize: 14 }}>加载对阵数据…</p>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "clamp(520px, calc(100vh - 300px), 700px)",
        minHeight: 0,
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${svgW} ${svgH}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ display: "block", overflow: "visible" }}
      >
              {STAGES.map((stage, index) => (
                <text
                  key={stage}
                  x={COL_X[index] + NODE_W / 2}
                  y={18}
                  textAnchor="middle"
                  fill="var(--color-text-muted)"
                  fontSize={12}
                  fontWeight={700}
                  letterSpacing="0.05em"
                >
                  {STAGE_LABELS[stage]}
                </text>
              ))}
              {flatMatches.map((fm) => {
                if (fm.stageIdx === 0) return null;
                const feeders = (fm.match.source_slots ?? [])
                  .map((sourceSlot) => matchesByKey.get(sourceSlot))
                  .filter((feeder): feeder is FlatMatch => feeder != null);
                const rx = COL_X[fm.stageIdx];
                const midX = rx - COL_GAP / 2;
                const ry = yCenter(fm.stageIdx, fm.matchIdx);
                return feeders.map((feeder) => {
                  const ly = yCenter(feeder.stageIdx, feeder.matchIdx);
                  const lx = COL_X[feeder.stageIdx] + NODE_W;
                  const delay = fm.stageIdx * 0.15 + feeder.matchIdx * 0.02;
                  return (
                    <motion.path key={`conn-${fm.match.match_key}-${feeder.match.match_key}`} d={`M${lx},${ly} H${midX} V${ry} H${rx}`} fill="none" stroke="var(--color-text-muted)" strokeWidth={1.2} strokeOpacity={0.35} initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 0.35 }} transition={{ delay, duration: 0.5, ease: "easeOut" }} />
                  );
                });
              })}
              {flatMatches.map((fm) => {
                const { match } = fm;
                const x = COL_X[fm.stageIdx];
                const y = yCenter(fm.stageIdx, fm.matchIdx) - NODE_H / 2;
                const isFinal = fm.stageIdx === STAGES.length - 1;
                const delay = fm.stageIdx * 0.18 + fm.matchIdx * 0.03;
                const matchKey = match.match_key ?? String(match.id);
                const isHovered = hoveredKey === matchKey;
                const homeWinner = match.winner_team_id === match.home_team?.id;
                const awayWinner = match.winner_team_id === match.away_team?.id;
                const strokeColor = isFinal || eventInfluenced
                  ? "var(--color-gold)"
                  : "var(--color-primary)";
                return (
                  <motion.g key={matchKey} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay, duration: 0.4, ease: "easeOut" }} onMouseEnter={() => setHoveredKey(matchKey)} onMouseLeave={() => setHoveredKey(null)} onClick={() => onMatchClick?.(match)} style={{ cursor: "pointer" }}>
                    <rect x={x} y={y} width={NODE_W} height={NODE_H} rx={6} fill={isHovered ? "#1e1e3a" : "var(--color-surface)"} stroke={strokeColor} strokeWidth={isHovered ? 2 : isFinal ? 2 : 1} style={{ transition: "fill 0.15s, stroke-width 0.15s" }} />
                    <text x={x + 8} y={y + 13} fill={homeWinner ? "var(--color-gold)" : "var(--color-text)"} fontSize={9.5} fontWeight={homeWinner ? 700 : 400} fontFamily="Inter, system-ui, sans-serif">
                      {match.home_team ? `${flagEmoji(match.home_team.fifa_code)} ${match.home_team.name_cn || match.home_team.name}` : "待定"}
                    </text>
                    <text x={x + NODE_W - 8} y={y + 13} fill={homeWinner ? "var(--color-gold)" : "var(--color-text)"} fontSize={10} fontWeight="bold" textAnchor="end" fontFamily="Inter, system-ui, sans-serif">{match.home_score ?? "-"}</text>
                    <line x1={x + 8} y1={y + NODE_H / 2} x2={x + NODE_W - 8} y2={y + NODE_H / 2} stroke="var(--color-text-muted)" strokeOpacity={0.15} />
                    <text x={x + 8} y={y + 31} fill={awayWinner ? "var(--color-gold)" : "var(--color-text)"} fontSize={9.5} fontWeight={awayWinner ? 700 : 400} fontFamily="Inter, system-ui, sans-serif">
                      {match.away_team ? `${flagEmoji(match.away_team.fifa_code)} ${match.away_team.name_cn || match.away_team.name}` : "待定"}
                    </text>
                    <text x={x + NODE_W - 8} y={y + 31} fill={awayWinner ? "var(--color-gold)" : "var(--color-text)"} fontSize={10} fontWeight="bold" textAnchor="end" fontFamily="Inter, system-ui, sans-serif">{match.away_score ?? "-"}</text>
                  </motion.g>
                );
              })}
              <AnimatePresence>
                {hoveredFlat && (
                  <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
                    <MatchDetailCard flatMatch={hoveredFlat} svgWidth={svgW} />
                  </motion.g>
                )}
              </AnimatePresence>
              <motion.text x={COL_X[STAGES.length - 1] + NODE_W / 2} y={yCenter(STAGES.length - 1, 0) - NODE_H / 2 - 20} textAnchor="middle" fontSize={28} initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 1.2, type: "spring", stiffness: 200 }}>🏆</motion.text>
      </svg>
      <div
        style={{
          position: "absolute",
          left: 8,
          bottom: 0,
          display: "flex",
          gap: 16,
          fontSize: 10,
          color: "var(--color-text-muted)",
          pointerEvents: "none",
        }}
      >
        <span>{eventInfluenced ? "金色：当前事件情景路径" : "蓝色：基线代表路径"}</span>
        <span>高亮球队：本场胜者</span>
        <span style={{ color: "var(--color-gold)" }}>金色：决赛</span>
      </div>
    </div>
  );
}
