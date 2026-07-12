import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import type {
  Match,
  AgentPrediction,
  BracketStage,
  Team,
} from "../types";

const STAGES = ["R32", "R16", "QF", "SF", "FINAL"] as const;

const STAGE_LABELS: Record<string, string> = {
  R32: "32 强",
  R16: "16 强",
  QF: "1/4 决赛",
  SF: "半决赛",
  FINAL: "决赛",
};

const NODE_W = 210;
const NODE_H = 56;
const COL_GAP = 64;
const MIN_GAP_Y = 14;
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

const TOTAL_H = stride(0) * 16;

function yCenter(stageIdx: number, matchIdx: number): number {
  const s = stride(stageIdx);
  return s * matchIdx + s / 2;
}

export function matchCount(stageIdx: number): number {
  return 16 >> stageIdx;
}

interface FlatMatch {
  match: Match;
  prediction: AgentPrediction | null;
  stageIdx: number;
  matchIdx: number;
  feederIndices: [number, number] | null;
}

function predictedWinner(
  match: Match,
  prediction: AgentPrediction | null,
  championProbs?: Record<string, number>,
): Team | null {
  const home = match.home_team;
  const away = match.away_team;
  if (!home || !away) return null;

  if (match.home_score != null && match.away_score != null) {
    if (match.home_score > match.away_score) return home;
    if (match.away_score > match.home_score) return away;
  }
  if (prediction?.winner === home.name) return home;
  if (prediction?.winner === away.name) return away;

  const homeProbability = championProbs?.[home.name] ?? 0;
  const awayProbability = championProbs?.[away.name] ?? 0;
  if (homeProbability !== awayProbability) {
    return homeProbability > awayProbability ? home : away;
  }
  return (home.elo_rating ?? 0) >= (away.elo_rating ?? 0) ? home : away;
}

function buildFlatMatches(
  stages: Record<string, BracketStage> | null,
  championProbs?: Record<string, number>,
  teams?: Team[],
): FlatMatch[] {
  const stageOrder = ["R32", "R16", "QF", "SF", "FINAL"];
  const result: FlatMatch[] = [];

  const teamsByName = new Map<string, Team>();
  teams?.forEach((team) => teamsByName.set(team.name, team));
  if (stages) {
    Object.values(stages).forEach((stage) => stage.matches.forEach((match) => {
      if (match.home_team) teamsByName.set(match.home_team.name, match.home_team);
      if (match.away_team) teamsByName.set(match.away_team.name, match.away_team);
    }));
  }

  const storedFirstRound = stages?.R32?.matches?.slice(0, 16) ?? [];
  if (storedFirstRound.length) {
    storedFirstRound.forEach((match, matchIdx) => result.push({
      match,
      prediction: match.prediction ?? null,
      stageIdx: 0,
      matchIdx,
      feederIndices: null,
    }));
  } else if (championProbs) {
    const sorted = Object.entries(championProbs).sort((a, b) => b[1] - a[1]).slice(0, 32);
    for (let i = 0; i < 16; i++) {
      const homeName = sorted[i * 2]?.[0] ?? "TBD";
      const awayName = sorted[i * 2 + 1]?.[0] ?? "TBD";
      result.push({
        match: {
          id: -(i + 1), stage: "R32", round_name: "32 强",
          home_team: teamsByName.get(homeName) ?? null,
          away_team: teamsByName.get(awayName) ?? null,
          home_score: null, away_score: null, is_simulated: false,
        },
        prediction: null, stageIdx: 0, matchIdx: i, feederIndices: null,
      });
    }
  }

  for (let stageIdx = 1; stageIdx < stageOrder.length; stageIdx++) {
    const previous = result.filter((fm) => fm.stageIdx === stageIdx - 1);
    const storedMatches = stages?.[stageOrder[stageIdx]]?.matches ?? [];
    for (let matchIdx = 0; matchIdx < matchCount(stageIdx); matchIdx++) {
      const stored = storedMatches[matchIdx];
      if (stored?.home_team && stored?.away_team) {
        result.push({
          match: stored,
          prediction: stored.prediction ?? null,
          stageIdx,
          matchIdx,
          feederIndices: [matchIdx * 2, matchIdx * 2 + 1],
        });
        continue;
      }

      const left = previous[matchIdx * 2];
      const right = previous[matchIdx * 2 + 1];
      result.push({
        match: {
          id: -(stageIdx * 100 + matchIdx + 1),
          stage: stageOrder[stageIdx],
          round_name: STAGE_LABELS[stageOrder[stageIdx]],
          home_team: left ? predictedWinner(left.match, left.prediction, championProbs) : null,
          away_team: right ? predictedWinner(right.match, right.prediction, championProbs) : null,
          home_score: null,
          away_score: null,
          is_simulated: false,
        },
        prediction: null,
        stageIdx,
        matchIdx,
        feederIndices: [matchIdx * 2, matchIdx * 2 + 1],
      });
    }
  }
  return result;
}

function MatchDetailCard({ flatMatch, svgWidth }: { flatMatch: FlatMatch; svgWidth: number }) {
  const { match, prediction } = flatMatch;
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
        {prediction && (
          <>
            <div style={{ borderTop: "1px solid #333", paddingTop: 8, marginBottom: 6 }}>
              <span style={{ color: prediction.is_agent ? "var(--color-gold)" : "var(--color-text-muted)" }}>
                {prediction.is_agent ? "🤖 Agent 预测" : "📊 泊松降级"}
              </span>
              <span style={{ float: "right", fontWeight: 600 }}>{((prediction.confidence ?? 0.5) * 100).toFixed(0)}%</span>
            </div>
            <div style={{ color: "var(--color-text-muted)", fontSize: 11, marginBottom: 4 }}>
              胜者: <strong style={{ color: "var(--color-text)" }}>{prediction.winner ?? "-"}</strong>
            </div>
            <div style={{ color: "var(--color-text-muted)", fontSize: 11, marginBottom: 4 }}>
              模型: <code style={{ color: "var(--color-accent)" }}>{prediction.model_used}</code>
            </div>
            {prediction.key_factors && (
              <div style={{ marginTop: 6 }}>
                {prediction.key_factors.slice(0, 3).map((f, i) => (
                  <div key={i} style={{ color: "var(--color-text-muted)", fontSize: 10, marginTop: 2 }}>· {f}</div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </foreignObject>
  );
}

interface BracketTreeProps {
  stages: Record<string, BracketStage> | null;
  championProbs?: Record<string, number>;
  teams?: Team[];
  eventInfluenced?: boolean;
  onMatchClick?: (match: Match, prediction: AgentPrediction | null) => void;
}

export default function BracketTree({ stages, championProbs, teams, eventInfluenced, onMatchClick }: BracketTreeProps) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const flatMatches = useMemo(
    () => buildFlatMatches(stages, championProbs, teams),
    [stages, championProbs, teams],
  );
  const svgW = COL_X[COL_X.length - 1] + NODE_W + 16;
  const svgH = TOTAL_H;
  const hoveredFlat = hoveredId != null ? flatMatches.find((f) => f.match.id === hoveredId) : null;
  const hasData = !!stages || !!championProbs;

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
    <TransformWrapper initialScale={1} minScale={0.3} maxScale={2.5} centerOnInit wheel={{ step: 0.1 }}>
      <TransformComponent wrapperStyle={{ width: "100%", height: "calc(100vh - 280px)" }}>
        <div style={{ position: "relative" }}>
          <div style={{ display: "flex", minWidth: svgW, paddingLeft: 8, marginBottom: 8, position: "relative", height: 24 }}>
            {STAGES.map((s, i) => (
              <div key={s} style={{ position: "absolute", left: COL_X[i] + 8, width: NODE_W, textAlign: "center", fontSize: 13, fontWeight: 700, color: "var(--color-text-muted)", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                {STAGE_LABELS[s]}
              </div>
            ))}
          </div>
          <div style={{ position: "relative", marginTop: 32 }}>
            <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`} style={{ display: "block" }}>
              {flatMatches.map((fm) => {
                if (fm.stageIdx === 0 || !fm.feederIndices) return null;
                const prevStage = fm.stageIdx - 1;
                const [fi1, fi2] = fm.feederIndices;
                const rx = COL_X[fm.stageIdx];
                const midX = rx - COL_GAP / 2;
                const ry = yCenter(fm.stageIdx, fm.matchIdx);
                return [fi1, fi2].map((fi, k) => {
                  const ly = yCenter(prevStage, fi);
                  const lx = COL_X[prevStage] + NODE_W;
                  const delay = fm.stageIdx * 0.15 + fi * 0.02;
                  return (
                    <motion.path key={`conn-${fm.match.id}-${k}`} d={`M${lx},${ly} H${midX} V${ry} H${rx}`} fill="none" stroke="var(--color-text-muted)" strokeWidth={1.2} strokeOpacity={0.35} initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 0.35 }} transition={{ delay, duration: 0.5, ease: "easeOut" }} />
                  );
                });
              })}
              {flatMatches.map((fm) => {
                const { match, prediction } = fm;
                const x = COL_X[fm.stageIdx];
                const y = yCenter(fm.stageIdx, fm.matchIdx) - NODE_H / 2;
                const isAgent = prediction?.is_agent ?? true;
                const isFinal = fm.stageIdx === STAGES.length - 1;
                const delay = fm.stageIdx * 0.18 + fm.matchIdx * 0.03;
                const isHovered = hoveredId === match.id;
                const strokeColor = isFinal ? "var(--color-gold)" : eventInfluenced ? "var(--color-gold)" : isAgent ? "var(--color-primary)" : "var(--color-text-muted)";
                return (
                  <motion.g key={match.id} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay, duration: 0.4, ease: "easeOut" }} onMouseEnter={() => setHoveredId(match.id)} onMouseLeave={() => setHoveredId(null)} onClick={() => onMatchClick?.(match, prediction)} style={{ cursor: "pointer" }}>
                    <rect x={x} y={y} width={NODE_W} height={NODE_H} rx={6} fill={isHovered ? "#1e1e3a" : "var(--color-surface)"} stroke={strokeColor} strokeWidth={isHovered ? 2 : isFinal ? 2 : 1} strokeDasharray={isAgent ? undefined : "5 3"} style={{ transition: "fill 0.15s, stroke-width 0.15s" }} />
                    <text x={x + 10} y={y + 19} fill="var(--color-text)" fontSize={11} fontFamily="Inter, system-ui, sans-serif">
                      {match.home_team ? `${flagEmoji(match.home_team.fifa_code)} ${match.home_team.name_cn || match.home_team.name}` : "TBD"}
                    </text>
                    <text x={x + NODE_W - 12} y={y + 19} fill="var(--color-text)" fontSize={12} fontWeight="bold" textAnchor="end" fontFamily="Inter, system-ui, sans-serif">{match.home_score ?? "-"}</text>
                    <line x1={x + 8} y1={y + NODE_H / 2} x2={x + NODE_W - 8} y2={y + NODE_H / 2} stroke="var(--color-text-muted)" strokeOpacity={0.15} />
                    <text x={x + 10} y={y + 44} fill="var(--color-text)" fontSize={11} fontFamily="Inter, system-ui, sans-serif">
                      {match.away_team ? `${flagEmoji(match.away_team.fifa_code)} ${match.away_team.name_cn || match.away_team.name}` : "TBD"}
                    </text>
                    <text x={x + NODE_W - 12} y={y + 44} fill="var(--color-text)" fontSize={12} fontWeight="bold" textAnchor="end" fontFamily="Inter, system-ui, sans-serif">{match.away_score ?? "-"}</text>
                    {prediction?.confidence != null && (
                      <g>
                        <rect x={x + NODE_W - 40} y={y + NODE_H / 2 - 7} width={30} height={14} rx={7} fill={isAgent ? "var(--color-gold)" : "var(--color-text-muted)"} fillOpacity={0.18} />
                        <text x={x + NODE_W - 25} y={y + NODE_H / 2 + 4} fill={isAgent ? "var(--color-gold)" : "var(--color-text-muted)"} fontSize={8} fontWeight="bold" textAnchor="middle" fontFamily="Inter, system-ui, sans-serif">{Math.round(prediction.confidence * 100)}%</text>
                      </g>
                    )}
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
          </div>
          <div style={{ display: "flex", gap: 24, marginTop: 16, paddingLeft: 8, fontSize: 12, color: "var(--color-text-muted)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <svg width={28} height={12}><rect x={0} y={0} width={28} height={12} rx={3} fill="var(--color-surface)" stroke="var(--color-primary)" strokeWidth={1} /></svg>
              <span>Agent 预测（实线）</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <svg width={28} height={12}><rect x={0} y={0} width={28} height={12} rx={3} fill="var(--color-surface)" stroke="var(--color-text-muted)" strokeWidth={1} strokeDasharray="4 2" /></svg>
              <span>泊松降级（虚线）</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <svg width={28} height={12}><rect x={0} y={0} width={28} height={12} rx={3} fill="var(--color-surface)" stroke="var(--color-gold)" strokeWidth={2} /></svg>
              <span>决赛</span>
            </div>
          </div>
        </div>
      </TransformComponent>
    </TransformWrapper>
  );
}
