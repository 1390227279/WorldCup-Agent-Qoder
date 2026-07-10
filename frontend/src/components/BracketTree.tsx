import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type {
  Match,
  AgentPrediction,
  BracketNode,
  Team,
} from "../types";

/* ================================================================
   Constants
   ================================================================ */

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

/* ================================================================
   Helpers
   ================================================================ */

/** Convert 3-letter FIFA code → flag emoji via Regional Indicator Symbols. */
function flagEmoji(code: string | undefined | null): string {
  if (!code || code.length < 2) return "🏳️";
  return code
    .toUpperCase()
    .slice(0, 2)
    .split("")
    .map((c) => String.fromCodePoint(0x1f1e6 + c.charCodeAt(0) - 65))
    .join("");
}

/** Compute vertical stride (center-to-center) for a given stage index. */
function stride(stageIdx: number): number {
  // R32 stride = NODE_H + MIN_GAP_Y = 70
  // Each subsequent round doubles
  return (NODE_H + MIN_GAP_Y) * Math.pow(2, stageIdx);
}

/** Total SVG height — determined by R32 (16 matches). */
const TOTAL_H = stride(0) * 16; // 1120

/** Y-center of match i in a given stage. */
function yCenter(stageIdx: number, matchIdx: number): number {
  const s = stride(stageIdx);
  return s * matchIdx + s / 2;
}

/** Number of matches per stage. */
function matchCount(stageIdx: number): number {
  return 16 >> stageIdx; // 16, 8, 4, 2, 1
}

/* ================================================================
   Flattened match data extracted from a BracketNode tree
   ================================================================ */

interface FlatMatch {
  match: Match;
  prediction: AgentPrediction | null;
  stageIdx: number;
  matchIdx: number;
  feederIndices: [number, number] | null; // match indices in previous stage
}

function flattenTree(root: BracketNode): FlatMatch[] {
  const result: FlatMatch[] = [];
  // Build a map: depth → matches in order
  const depthMap = new Map<number, BracketNode[]>();

  function walk(node: BracketNode) {
    const d = node.depth;
    if (!depthMap.has(d)) depthMap.set(d, []);
    depthMap.get(d)!.push(node);
    if (node.left) walk(node.left);
    if (node.right) walk(node.right);
  }
  walk(root);

  // The FINAL has depth 0 (or the smallest). We need to invert:
  // depth 0 = FINAL, depth 1 = SF, ... depth 4 = R32
  // stageIdx: R32=0, R16=1, QF=2, SF=3, FINAL=4
  const maxDepth = Math.max(...depthMap.keys());

  for (const [depth, nodes] of depthMap) {
    const stageIdx = maxDepth - depth;
    for (let mi = 0; mi < nodes.length; mi++) {
      const node = nodes[mi];
      // feeder indices: each match at stageIdx receives from 2 matches at stageIdx-1
      const feederIndices: [number, number] | null =
        stageIdx > 0 ? [mi * 2, mi * 2 + 1] : null;

      result.push({
        match: node.match,
        prediction: node.prediction,
        stageIdx,
        matchIdx: mi,
        feederIndices,
      });
    }
  }

  return result.sort((a, b) => a.stageIdx - b.stageIdx || a.matchIdx - b.matchIdx);
}

/* ================================================================
   Demo data generator (used when no real data is available)
   ================================================================ */

function makeTeam(id: number, name: string, code: string, elo: number): Team {
  return {
    id, name, name_cn: name, fifa_code: code, confederation: "UEFA",
    fifa_ranking: null, elo_rating: elo, group_name: null, pot: null, stats: null,
  };
}

const DEMO_TEAMS: Team[] = [
  makeTeam(1, "Argentina", "ARG", 2143),
  makeTeam(2, "France", "FRA", 2090),
  makeTeam(3, "Brazil", "BRA", 2050),
  makeTeam(4, "England", "ENG", 2040),
  makeTeam(5, "Spain", "ESP", 2030),
  makeTeam(6, "Germany", "GER", 2010),
  makeTeam(7, "Netherlands", "NED", 1990),
  makeTeam(8, "Portugal", "POR", 1980),
  makeTeam(9, "Belgium", "BEL", 1960),
  makeTeam(10, "Croatia", "CRO", 1950),
  makeTeam(11, "Italy", "ITA", 1940),
  makeTeam(12, "Uruguay", "URU", 1920),
  makeTeam(13, "USA", "USA", 1870),
  makeTeam(14, "Mexico", "MEX", 1860),
  makeTeam(15, "Japan", "JPN", 1850),
  makeTeam(16, "Senegal", "SEN", 1830),
  makeTeam(17, "Morocco", "MAR", 1880),
  makeTeam(18, "Denmark", "DEN", 1870),
  makeTeam(19, "Switzerland", "SUI", 1850),
  makeTeam(20, "Korea Republic", "KOR", 1820),
  makeTeam(21, "Australia", "AUS", 1790),
  makeTeam(22, "Serbia", "SRB", 1810),
  makeTeam(23, "Poland", "POL", 1800),
  makeTeam(24, "Colombia", "COL", 1840),
  makeTeam(25, "Ecuador", "ECU", 1770),
  makeTeam(26, "Canada", "CAN", 1760),
  makeTeam(27, "Ghana", "GHA", 1750),
  makeTeam(28, "Nigeria", "NGA", 1780),
  makeTeam(29, "Cameroon", "CMR", 1740),
  makeTeam(30, "Tunisia", "TUN", 1730),
  makeTeam(31, "Saudi Arabia", "KSA", 1700),
  makeTeam(32, "Costa Rica", "CRC", 1690),
];

function generateDemoTree(): BracketNode {
  let nextId = 1;

  function buildMatch(
    home: Team | null,
    away: Team | null,
    stage: string,
    depth: number,
    homeScore: number | null,
    awayScore: number | null,
    isAgent: boolean,
    confidence: number,
  ): BracketNode {
    const match: Match = {
      id: nextId++,
      stage,
      round_name: STAGE_LABELS[stage] ?? stage,
      home_team: home,
      away_team: away,
      home_score: homeScore,
      away_score: awayScore,
      is_simulated: true,
    };
    const prediction: AgentPrediction | null = home && away
      ? {
          id: nextId,
          match_id: match.id,
          winner: (homeScore ?? 0) >= (awayScore ?? 0) ? home.name : away.name,
          predicted_score: `${homeScore ?? 0}-${awayScore ?? 0}`,
          confidence,
          key_factors: ["ELO 评分差距分析", "近期状态评估", "历史交锋数据"],
          reasoning_chain: [],
          is_agent: isAgent,
          model_used: isAgent ? "qwen-max" : "poisson",
        }
      : null;

    return { match, prediction, left: null, right: null, depth, children: null };
  }

  // R32 matchups (16 matches, seeded)
  const pairings: [number, number, number, number, boolean][] = [
    [0, 31, 3, 1, true],   // ARG vs CRC
    [15, 16, 1, 2, true],  // SEN vs MAR
    [2, 29, 2, 0, true],   // BRA vs TUN
    [13, 18, 1, 1, false], // MEX vs SUI
    [4, 27, 2, 1, true],   // ESP vs NGA
    [11, 20, 1, 0, false], // URU vs AUS
    [6, 25, 2, 0, true],   // NED vs ECU
    [9, 22, 1, 1, false],  // CRO vs POL
    [1, 30, 3, 0, true],   // FRA vs KSA
    [14, 17, 1, 2, true],  // JPN vs DEN
    [3, 28, 2, 1, true],   // ENG vs CMR
    [12, 19, 1, 0, false], // USA vs KOR
    [5, 26, 3, 1, true],   // GER vs GHA
    [10, 21, 2, 0, true],  // ITA vs SRB
    [7, 24, 2, 1, false],  // POR vs COL (Poisson fallback demo)
    [8, 23, 1, 0, true],   // BEL vs CAN (no score yet — TBD)
  ];

  // Build R32 nodes (depth 4)
  const r32: BracketNode[] = pairings.map(
    ([hi, ai, hs, as_, agent]) =>
      buildMatch(DEMO_TEAMS[hi], DEMO_TEAMS[ai], "R32", 4, hs, as_, agent, 0.55 + Math.random() * 0.3),
  );

  // Simulated winners advancing
  function winner(n: BracketNode): Team | null {
    if (!n.match.home_team || !n.match.away_team) return n.match.home_team;
    return (n.match.home_score ?? 0) >= (n.match.away_score ?? 0)
      ? n.match.home_team
      : n.match.away_team;
  }

  // R16 (depth 3)
  const r16: BracketNode[] = [];
  for (let i = 0; i < r32.length; i += 2) {
    const w1 = winner(r32[i]);
    const w2 = winner(r32[i + 1]);
    const node = buildMatch(w1, w2, "R16", 3, i < 8 ? 2 : null, i < 8 ? 1 : null, true, 0.6);
    node.left = r32[i];       // upper feeder
    node.right = r32[i + 1];  // lower feeder
    r16.push(node);
  }

  // QF (depth 2)
  const qf: BracketNode[] = [];
  for (let i = 0; i < r16.length; i += 2) {
    const w1 = winner(r16[i]);
    const w2 = winner(r16[i + 1]);
    const node = buildMatch(w1, w2, "QF", 2, i < 4 ? 2 : null, i < 4 ? 0 : null, true, 0.65);
    node.left = r16[i];
    node.right = r16[i + 1];
    qf.push(node);
  }

  // SF (depth 1)
  const sf: BracketNode[] = [];
  for (let i = 0; i < qf.length; i += 2) {
    const w1 = winner(qf[i]);
    const w2 = winner(qf[i + 1]);
    const node = buildMatch(w1, w2, "SF", 1, i === 0 ? 1 : null, i === 0 ? 2 : null, true, 0.58);
    node.left = qf[i];
    node.right = qf[i + 1];
    sf.push(node);
  }

  // FINAL (depth 0)
  const w1 = winner(sf[0]);
  const w2 = winner(sf[1]);
  const final = buildMatch(w1, w2, "FINAL", 0, 2, 1, true, 0.72);
  final.left = sf[0];
  final.right = sf[1];

  return final;
}

/* ================================================================
   Match Detail Popup
   ================================================================ */

function MatchDetailCard({
  flatMatch,
  svgWidth,
}: {
  flatMatch: FlatMatch;
  svgWidth: number;
}) {
  const { match, prediction } = flatMatch;
  const x = COL_X[flatMatch.stageIdx];
  const y = yCenter(flatMatch.stageIdx, flatMatch.matchIdx);

  // Position popup to the right of the node (or left if too close to edge)
  const popLeft = x + NODE_W + 12 > svgWidth - 260 ? x - 260 : x + NODE_W + 12;
  const popTop = Math.max(8, Math.min(y - 80, TOTAL_H - 260));

  return (
    <foreignObject x={popLeft} y={popTop} width={250} height={250}>
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-primary)",
          borderRadius: 12,
          padding: 14,
          fontSize: 12,
          color: "var(--color-text)",
          boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>
          {STAGE_LABELS[match.stage] ?? match.stage}
        </div>

        {/* Teams */}
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span>{flagEmoji(match.home_team?.fifa_code)} {match.home_team?.name ?? "TBD"}</span>
          <span style={{ fontWeight: 700 }}>{match.home_score ?? "-"}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
          <span>{flagEmoji(match.away_team?.fifa_code)} {match.away_team?.name ?? "TBD"}</span>
          <span style={{ fontWeight: 700 }}>{match.away_score ?? "-"}</span>
        </div>

        {prediction && (
          <>
            <div style={{ borderTop: "1px solid #333", paddingTop: 8, marginBottom: 6 }}>
              <span style={{ color: prediction.is_agent ? "var(--color-gold)" : "var(--color-text-muted)" }}>
                {prediction.is_agent ? "🤖 Agent 预测" : "📊 泊松降级"}
              </span>
              <span style={{ float: "right", fontWeight: 600 }}>
                {((prediction.confidence ?? 0.5) * 100).toFixed(0)}%
              </span>
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
                  <div key={i} style={{ color: "var(--color-text-muted)", fontSize: 10, marginTop: 2 }}>
                    · {f}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </foreignObject>
  );
}

/* ================================================================
   Main Component
   ================================================================ */

interface BracketTreeProps {
  root?: BracketNode | null;
  onMatchClick?: (match: Match, prediction: AgentPrediction | null) => void;
}

export default function BracketTree({ root, onMatchClick }: BracketTreeProps) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  // Use provided tree or generate demo data
  const tree = root ?? useMemo(() => generateDemoTree(), []);

  // Flatten tree into renderable list
  const flatMatches = useMemo(() => flattenTree(tree), [tree]);

  // SVG dimensions
  const svgW = COL_X[COL_X.length - 1] + NODE_W + 16;
  const svgH = TOTAL_H;

  // Build lookup for hovered match
  const hoveredFlat = hoveredId != null ? flatMatches.find((f) => f.match.id === hoveredId) : null;

  return (
    <div style={{ overflowX: "auto", overflowY: "auto", padding: "24px 0" }}>
      {/* Stage column headers */}
      <div style={{ display: "flex", minWidth: svgW, paddingLeft: 8, marginBottom: 8 }}>
        {STAGES.map((s, i) => (
          <div
            key={s}
            style={{
              position: "absolute",
              left: COL_X[i] + 8,
              width: NODE_W,
              textAlign: "center",
              fontSize: 13,
              fontWeight: 700,
              color: "var(--color-text-muted)",
              letterSpacing: "0.05em",
              textTransform: "uppercase",
            }}
          >
            {STAGE_LABELS[s]}
          </div>
        ))}
      </div>

      <div style={{ position: "relative", marginTop: 32 }}>
        <svg
          width={svgW}
          height={svgH}
          viewBox={`0 0 ${svgW} ${svgH}`}
          style={{ display: "block" }}
        >
          {/* ── Connector lines ── */}
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
                <motion.path
                  key={`conn-${fm.match.id}-${k}`}
                  d={`M${lx},${ly} H${midX} V${ry} H${rx}`}
                  fill="none"
                  stroke="var(--color-text-muted)"
                  strokeWidth={1.2}
                  strokeOpacity={0.35}
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 0.35 }}
                  transition={{ delay, duration: 0.5, ease: "easeOut" }}
                />
              );
            });
          })}

          {/* ── Match nodes ── */}
          {flatMatches.map((fm) => {
            const { match, prediction } = fm;
            const x = COL_X[fm.stageIdx];
            const y = yCenter(fm.stageIdx, fm.matchIdx) - NODE_H / 2;
            const isAgent = prediction?.is_agent ?? true;
            const isFinal = fm.stageIdx === STAGES.length - 1;
            const delay = fm.stageIdx * 0.18 + fm.matchIdx * 0.03;
            const isHovered = hoveredId === match.id;

            // Border color
            const strokeColor = isFinal
              ? "var(--color-gold)"
              : isAgent
                ? "var(--color-primary)"
                : "var(--color-text-muted)";

            return (
              <motion.g
                key={match.id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay, duration: 0.4, ease: "easeOut" }}
                onMouseEnter={() => setHoveredId(match.id)}
                onMouseLeave={() => setHoveredId(null)}
                onClick={() => onMatchClick?.(match, prediction)}
                style={{ cursor: "pointer" }}
              >
                {/* Background rect */}
                <rect
                  x={x}
                  y={y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={6}
                  fill={isHovered ? "#1e1e3a" : "var(--color-surface)"}
                  stroke={strokeColor}
                  strokeWidth={isHovered ? 2 : isFinal ? 2 : 1}
                  strokeDasharray={isAgent ? undefined : "5 3"}
                  style={{ transition: "fill 0.15s, stroke-width 0.15s" }}
                />

                {/* Home team row */}
                <text
                  x={x + 10}
                  y={y + 19}
                  fill="var(--color-text)"
                  fontSize={11}
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {match.home_team
                    ? `${flagEmoji(match.home_team.fifa_code)} ${match.home_team.fifa_code}`
                    : "TBD"}
                </text>
                <text
                  x={x + NODE_W - 12}
                  y={y + 19}
                  fill="var(--color-text)"
                  fontSize={12}
                  fontWeight="bold"
                  textAnchor="end"
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {match.home_score ?? "-"}
                </text>

                {/* Divider */}
                <line
                  x1={x + 8}
                  y1={y + NODE_H / 2}
                  x2={x + NODE_W - 8}
                  y2={y + NODE_H / 2}
                  stroke="var(--color-text-muted)"
                  strokeOpacity={0.15}
                />

                {/* Away team row */}
                <text
                  x={x + 10}
                  y={y + 44}
                  fill="var(--color-text)"
                  fontSize={11}
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {match.away_team
                    ? `${flagEmoji(match.away_team.fifa_code)} ${match.away_team.fifa_code}`
                    : "TBD"}
                </text>
                <text
                  x={x + NODE_W - 12}
                  y={y + 44}
                  fill="var(--color-text)"
                  fontSize={12}
                  fontWeight="bold"
                  textAnchor="end"
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {match.away_score ?? "-"}
                </text>

                {/* Confidence badge */}
                {prediction?.confidence != null && (
                  <g>
                    <rect
                      x={x + NODE_W - 40}
                      y={y + NODE_H / 2 - 7}
                      width={30}
                      height={14}
                      rx={7}
                      fill={isAgent ? "var(--color-gold)" : "var(--color-text-muted)"}
                      fillOpacity={0.18}
                    />
                    <text
                      x={x + NODE_W - 25}
                      y={y + NODE_H / 2 + 4}
                      fill={isAgent ? "var(--color-gold)" : "var(--color-text-muted)"}
                      fontSize={8}
                      fontWeight="bold"
                      textAnchor="middle"
                      fontFamily="Inter, system-ui, sans-serif"
                    >
                      {Math.round(prediction.confidence * 100)}%
                    </text>
                  </g>
                )}
              </motion.g>
            );
          })}

          {/* ── Detail popup on hover ── */}
          <AnimatePresence>
            {hoveredFlat && (
              <motion.g
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                <MatchDetailCard flatMatch={hoveredFlat} svgWidth={svgW} />
              </motion.g>
            )}
          </AnimatePresence>

          {/* ── Trophy at the Final ── */}
          <motion.text
            x={COL_X[STAGES.length - 1] + NODE_W / 2}
            y={yCenter(STAGES.length - 1, 0) - NODE_H / 2 - 20}
            textAnchor="middle"
            fontSize={28}
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 1.2, type: "spring", stiffness: 200 }}
          >
            🏆
          </motion.text>
        </svg>
      </div>

      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: 24,
          marginTop: 16,
          paddingLeft: 8,
          fontSize: 12,
          color: "var(--color-text-muted)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <svg width={28} height={12}>
            <rect x={0} y={0} width={28} height={12} rx={3} fill="var(--color-surface)" stroke="var(--color-primary)" strokeWidth={1} />
          </svg>
          <span>Agent 预测（实线）</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <svg width={28} height={12}>
            <rect x={0} y={0} width={28} height={12} rx={3} fill="var(--color-surface)" stroke="var(--color-text-muted)" strokeWidth={1} strokeDasharray="4 2" />
          </svg>
          <span>泊松降级（虚线）</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <svg width={28} height={12}>
            <rect x={0} y={0} width={28} height={12} rx={3} fill="var(--color-surface)" stroke="var(--color-gold)" strokeWidth={2} />
          </svg>
          <span>决赛</span>
        </div>
      </div>
    </div>
  );
}
