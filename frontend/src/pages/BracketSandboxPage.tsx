import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import BracketTree from "../components/BracketTree";
import ScenarioSlider from "../components/ScenarioSlider";
import AIPunditPanel from "../components/AIPunditPanel";
import { usePredictions } from "../hooks/usePredictions";
import { api } from "../services/api";
import type { Match, AgentPrediction, SimulationResult } from "../types";

export default function BracketSandboxPage() {
  const [selectedEventIds, setSelectedEventIds] = useState<number[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [selectedPrediction, setSelectedPrediction] = useState<AgentPrediction | null>(null);
  const [isRefreshingSimulation, setIsRefreshingSimulation] = useState(false);
  const queryClient = useQueryClient();

  const {
    mutate: predictMatch,
    data: mutationResult,
    isPending,
    error: predictError,
  } = usePredictions();

  const eventKey = selectedEventIds.join(",");
  const simulationQueryKey = ["simulation", eventKey] as const;
  const {
    data: simulation,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery<SimulationResult>({
    queryKey: simulationQueryKey,
    queryFn: () => api.getSimulation({ event_ids: eventKey || undefined }),
    staleTime: 5 * 60 * 1000,
  });

  const applyEventSelection = async (eventIds: number[]) => {
    const nextEventKey = eventIds.join(",");
    const refreshed = await api.getSimulation({
      event_ids: nextEventKey || undefined,
      refresh: true,
    });
    queryClient.setQueryData(["simulation", nextEventKey], refreshed);
    setSelectedEventIds(eventIds);
  };

  const refreshSimulation = async () => {
    setIsRefreshingSimulation(true);
    try {
      const refreshed = await api.getSimulation({
        event_ids: eventKey || undefined,
        refresh: true,
      });
      queryClient.setQueryData(simulationQueryKey, refreshed);
    } finally {
      setIsRefreshingSimulation(false);
    }
  };

  const handleMatchClick = useCallback(
    (match: Match, prediction: AgentPrediction | null) => {
      setSelectedMatch(match);
      setSelectedPrediction(prediction);
      if (
        !prediction &&
        match.home_team &&
        match.away_team &&
        match.home_team.id > 0 &&
        match.away_team.id > 0
      ) {
        predictMatch({
          homeTeam: match.home_team,
          awayTeam: match.away_team,
        });
      }
    },
    [predictMatch],
  );

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
        reasoning_chain: p.reasoning_chain.map((r, index) => ({
          step_number: r.step_number > 0 ? r.step_number : index + 1,
          tool_used: r.tool_used,
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

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-4">
      <Link
        to="/"
        className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors mb-3 inline-block"
      >
        ← 返回首页
      </Link>

      <header className="mb-3">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-bold mb-1">🏟️ 淘汰赛推演</h1>
          <button
            onClick={refreshSimulation}
            disabled={isRefreshingSimulation}
            className="text-xs px-3 py-2 rounded-lg bg-[var(--color-primary)] text-white disabled:opacity-50"
          >
            {isRefreshingSimulation ? "重新模拟中…" : "重新模拟"}
          </button>
        </div>
        <p className="text-[var(--color-text-muted)]">
          {selectedEventIds.length > 0 ? "当前情景模拟" : "默认赛事模拟"}
          {simulation?.simulation_id ? ` · 模拟编号 ${simulation.simulation_id.slice(0, 8)}` : ""}
        </p>
      </header>

      <ScenarioSlider selectedEventIds={selectedEventIds} onChange={applyEventSelection} />

      <div className="flex gap-4 items-start flex-col xl:flex-row">
        <div className="flex-1 min-w-0 bg-[var(--color-surface)] rounded-xl p-3 overflow-hidden relative">
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

          {!error && (
            <>
              {isFetching && !isLoading && (
                <div className="absolute top-3 right-3 text-xs text-[var(--color-text-muted)] animate-pulse">
                  刷新中…
                </div>
              )}
              <BracketTree
                stages={simulation?.stages ?? null}
                eventInfluenced={selectedEventIds.length > 0}
                onMatchClick={handleMatchClick}
              />
            </>
          )}
        </div>

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
                    <span>{selectedMatch.home_team?.name_cn ?? "待定"}</span>
                    <span className="text-[var(--color-text-muted)] mx-2">对阵</span>
                    <span>{selectedMatch.away_team?.name_cn ?? "待定"}</span>
                  </div>
                  {selectedMatch.home_score != null && (
                    <div className="text-center text-lg font-bold mt-1 font-mono">
                      {selectedMatch.home_score} - {selectedMatch.away_score}
                    </div>
                  )}
                </div>

                {isPending && (
                  <div className="bg-[var(--color-surface)] rounded-xl p-4 text-center">
                    <motion.div
                      animate={{ opacity: [0.4, 1, 0.4] }}
                      transition={{ repeat: Infinity, duration: 1.5 }}
                      className="text-sm text-[var(--color-text-muted)]"
                    >
                      🤖 正在分析比赛…
                    </motion.div>
                  </div>
                )}

                {predictError && (
                  <div className="bg-[var(--color-surface)] rounded-xl p-4 text-center mb-3">
                    <p className="text-sm text-[var(--color-accent)]">
                      预测请求失败：
                      {predictError instanceof Error ? predictError.message : "未知错误"}
                    </p>
                  </div>
                )}

                {!isPending && (
                  <AIPunditPanel
                    prediction={effectivePrediction}
                    homeTeam={selectedMatch.home_team}
                    awayTeam={selectedMatch.away_team}
                  />
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
