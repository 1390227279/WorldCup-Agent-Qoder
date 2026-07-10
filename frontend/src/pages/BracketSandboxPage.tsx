import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";

import BracketTree from "../components/BracketTree";
import ScenarioSlider, { type Scenario } from "../components/ScenarioSlider";
import AIPunditPanel from "../components/AIPunditPanel";
import { useBracket } from "../hooks/useBracket";
import { usePredictions } from "../hooks/usePredictions";
import type { Match, AgentPrediction } from "../types";

export default function BracketSandboxPage() {
  // ── 状态 ──
  const [selectedScenario, setSelectedScenario] = useState<string>("default");
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [selectedPrediction, setSelectedPrediction] =
    useState<AgentPrediction | null>(null);

  // ── Hooks（直接返回 TanStack Query 对象）──
  const {
    data: bracket,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useBracket();

  const {
    mutate: predictMatch,
    data: mutationResult,
    isPending,
    error: predictError,
  } = usePredictions();

  // ── 点击比赛节点 ──
  const handleMatchClick = useCallback(
    (match: Match, prediction: AgentPrediction | null) => {
      setSelectedMatch(match);
      setSelectedPrediction(prediction);

      // 没有现成预测数据 → 调 API 实时预测
      if (!prediction && match.home_team && match.away_team) {
        predictMatch({
          homeTeamId: match.home_team.id,
          awayTeamId: match.away_team.id,
        });
      }
    },
    [predictMatch],
  );

  // ── 切换情景 ──
  const handleScenarioChange = useCallback((scenario: Scenario) => {
    setSelectedScenario(scenario.id);
    setSelectedMatch(null);
    setSelectedPrediction(null);
    // 后端 Phase 4 接入后：api.recalculate({ scenario_id: scenario.id })
  }, []);

  // ── 将 mutation 结果适配为 AgentPrediction ──
  const effectivePrediction: AgentPrediction | null = (() => {
    if (selectedPrediction) return selectedPrediction;
    const mp = mutationResult;
    if (mp?.prediction) {
      const p = mp.prediction;
      return {
        id: 0,
        match_id: selectedMatch?.id ?? 0,
        winner: p.winner,
        predicted_score: p.predicted_score,
        confidence: p.confidence,
        key_factors: p.key_factors,
        reasoning_chain: p.reasoning_chain.map((r) => ({
          step: r.step ?? 0,
          tool: r.tool,
          finding: r.finding,
          analysis: r.analysis,
        })),
        is_agent: mp.is_agent,
        model_used: mp.model_used,
        tool_calls_log: p.tool_calls_log,
      };
    }
    return null;
  })();

  // ── 渲染 ──
  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8">
      <Link
        to="/"
        className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors mb-6 inline-block"
      >
        ← 返回首页
      </Link>

      <header className="mb-6">
        <h1 className="text-3xl font-bold mb-2">🏟️ Bracket Sandbox</h1>
        <p className="text-[var(--color-text-muted)]">
          交互式淘汰赛推演沙盘 · 五层对阵树 · AI Agent 预测可视化
        </p>
      </header>

      {/* Scenario Slider */}
      <ScenarioSlider defaultId={selectedScenario} onChange={handleScenarioChange} />

      {/* Main: Bracket + Side Panel */}
      <div className="flex gap-6 items-start flex-col xl:flex-row">
        {/* ── Bracket Tree ── */}
        <div className="flex-1 min-w-0 bg-[var(--color-surface)] rounded-xl p-6 overflow-hidden relative">
          {/* Loading */}
          {isLoading && (
            <div className="flex items-center justify-center py-24">
              <div className="text-center">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
                  className="text-4xl mb-3"
                >
                  ⚽
                </motion.div>
                <p className="text-[var(--color-text-muted)] text-sm">加载对阵数据…</p>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="text-center py-16">
              <p className="text-4xl mb-3">❌</p>
              <p className="text-[var(--color-accent)] text-sm mb-3">
                {error instanceof Error ? error.message : "加载失败"}
              </p>
              <button
                onClick={() => refetch()}
                className="text-xs px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity"
              >
                重试
              </button>
            </div>
          )}

          {/* Bracket */}
          {!error && (
            <>
              {isFetching && !isLoading && (
                <div className="absolute top-3 right-3 text-xs text-[var(--color-text-muted)] animate-pulse">
                  刷新中…
                </div>
              )}
              <BracketTree
                root={null /* 后端 BracketResponse → tree 转换待 Phase 4 */}
                onMatchClick={handleMatchClick}
              />
            </>
          )}
        </div>

        {/* ── AI Pundit Side Panel ── */}
        <div className="w-full xl:w-[360px] flex-shrink-0">
          <AnimatePresence mode="wait">
            {selectedMatch ? (
              <motion.div
                key={selectedMatch.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
              >
                {/* Match header */}
                <div className="bg-[var(--color-surface)] rounded-xl p-4 mb-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">
                      {selectedMatch.round_name ?? selectedMatch.stage}
                    </span>
                    <button
                      onClick={() => {
                        setSelectedMatch(null);
                        setSelectedPrediction(null);
                      }}
                      className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-xs"
                    >
                      ✕ 关闭
                    </button>
                  </div>
                  <div className="flex items-center justify-between text-sm font-medium">
                    <span>
                      {selectedMatch.home_team?.name_cn ?? selectedMatch.home_team?.name ?? "TBD"}
                    </span>
                    <span className="text-[var(--color-text-muted)] mx-2">vs</span>
                    <span>
                      {selectedMatch.away_team?.name_cn ?? selectedMatch.away_team?.name ?? "TBD"}
                    </span>
                  </div>
                  {selectedMatch.home_score != null && (
                    <div className="text-center text-lg font-bold mt-1 font-mono">
                      {selectedMatch.home_score} - {selectedMatch.away_score}
                    </div>
                  )}
                </div>

                {/* Predicting */}
                {isPending && (
                  <div className="bg-[var(--color-surface)] rounded-xl p-4 text-center">
                    <motion.div
                      animate={{ opacity: [0.4, 1, 0.4] }}
                      transition={{ repeat: Infinity, duration: 1.5 }}
                      className="text-sm text-[var(--color-text-muted)]"
                    >
                      🤖 Agent 正在分析…
                    </motion.div>
                  </div>
                )}

                {/* Prediction error */}
                {predictError && (
                  <div className="bg-[var(--color-surface)] rounded-xl p-4 text-center mb-3">
                    <p className="text-sm text-[var(--color-accent)]">
                      预测请求失败：
                      {predictError instanceof Error
                        ? predictError.message
                        : "未知错误"}
                    </p>
                  </div>
                )}

                {/* AI Pundit */}
                {!isPending && (
                  <AIPunditPanel prediction={effectivePrediction} />
                )}
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <AIPunditPanel prediction={null} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
