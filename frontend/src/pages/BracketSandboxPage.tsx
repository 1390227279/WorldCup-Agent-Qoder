import { useState, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import BracketTree from "../components/BracketTree";
import ScenarioSlider from "../components/ScenarioSlider";
import AIPunditPanel from "../components/AIPunditPanel";
import { usePredictions } from "../hooks/usePredictions";
import { api, simulationQueryKeys } from "../services/api";
import type { Match, SimulationResult } from "../types";

export default function BracketSandboxPage() {
  const [selectedEventIds, setSelectedEventIds] = useState<number[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [scenarioSimulation, setScenarioSimulation] = useState<SimulationResult | null>(null);
  const [isRefreshingSimulation, setIsRefreshingSimulation] = useState(false);
  const [refreshError, setRefreshError] = useState<Error | null>(null);
  const queryClient = useQueryClient();

  const {
    mutate: predictMatch,
    data: mutationResult,
    isPending,
    error: predictError,
    reset: resetPrediction,
  } = usePredictions();

  const {
    data: baselineSimulation,
    isLoading,
    isFetching: isFetchingBaseline,
    error: baselineError,
    refetch: refetchBaseline,
  } = useQuery<SimulationResult>({
    queryKey: simulationQueryKeys.baseline,
    queryFn: () => api.getSimulation(),
    staleTime: 5 * 60 * 1000,
  });

  const simulation = selectedEventIds.length > 0
    ? scenarioSimulation
    : baselineSimulation;
  const error = baselineError ?? refreshError;
  const isFetching = isFetchingBaseline || isRefreshingSimulation;

  const applyEventSelection = async (eventIds: number[]) => {
    const normalizedIds = [...new Set(eventIds)].sort((a, b) => a - b);
    setRefreshError(null);

    if (normalizedIds.length === 0) {
      setSelectedEventIds([]);
      setScenarioSimulation(null);
      setSelectedMatch(null);
      resetPrediction();
      return;
    }
    if (!baselineSimulation) {
      throw new Error("基线模拟尚未加载完成，请稍后重试");
    }

    const refreshed = await api.getSimulation({
      event_ids: normalizedIds,
      baseline_simulation_id: baselineSimulation.simulation_id,
      refresh: true,
    });
    queryClient.setQueryData(
      simulationQueryKeys.scenario(baselineSimulation.simulation_id, normalizedIds),
      refreshed,
    );
    setScenarioSimulation(refreshed);
    setSelectedEventIds(normalizedIds);
    setSelectedMatch(null);
    resetPrediction();
  };

  const refreshSimulation = async () => {
    setIsRefreshingSimulation(true);
    setRefreshError(null);
    try {
      const refreshedBaseline = await api.getSimulation({ refresh: true });
      queryClient.setQueryData(simulationQueryKeys.baseline, refreshedBaseline);

      if (selectedEventIds.length > 0) {
        const refreshedScenario = await api.getSimulation({
          event_ids: selectedEventIds,
          baseline_simulation_id: refreshedBaseline.simulation_id,
          refresh: true,
        });
        queryClient.setQueryData(
          simulationQueryKeys.scenario(
            refreshedBaseline.simulation_id,
            selectedEventIds,
          ),
          refreshedScenario,
        );
        setScenarioSimulation(refreshedScenario);
      } else {
        setScenarioSimulation(null);
      }
      setSelectedMatch(null);
      resetPrediction();
    } catch (caughtError) {
      setRefreshError(
        caughtError instanceof Error ? caughtError : new Error("重新模拟失败"),
      );
    } finally {
      setIsRefreshingSimulation(false);
    }
  };

  const handleMatchClick = useCallback(
    (match: Match) => {
      setSelectedMatch(match);
      resetPrediction();
      if (
        simulation?.simulation_id &&
        match.match_key
      ) {
        predictMatch({
          simulationId: simulation.simulation_id,
          matchKey: match.match_key,
        });
      }
    },
    [predictMatch, resetPrediction, simulation],
  );

  const scenarioComparison = useMemo(() => {
    if (
      !baselineSimulation ||
      !scenarioSimulation ||
      scenarioSimulation.scenario.type !== "EVENT"
    ) {
      return null;
    }
    const affectedTeamIds = [...new Set(
      scenarioSimulation.scenario.applied_events.map((event) => event.team_id),
    )];
    return {
      events: scenarioSimulation.scenario.applied_events,
      ignoredCount: scenarioSimulation.scenario.ignored_events.length,
      teams: affectedTeamIds.map((teamId) => {
        const scenarioAdvancement = scenarioSimulation.summary.advancement_probs[teamId];
        const baselineAdvancement = baselineSimulation.summary.advancement_probs[teamId];
        const baselineProbability = (
          baselineSimulation.summary.champion_probs_by_team_id[teamId] ?? 0
        );
        const scenarioProbability = (
          scenarioSimulation.summary.champion_probs_by_team_id[teamId] ?? 0
        );
        return {
          teamId,
          team: scenarioAdvancement?.team ?? baselineAdvancement?.team,
          probability: scenarioProbability,
          deltaPoints: (scenarioProbability - baselineProbability) * 100,
        };
      }),
    };
  }, [baselineSimulation, scenarioSimulation]);

  const selectedAnalysis = (
    mutationResult &&
    selectedMatch?.match_key === mutationResult.match_key &&
    simulation?.simulation_id === mutationResult.simulation_id
  ) ? mutationResult : null;

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
          {simulation?.scenario.type === "EVENT" ? "当前事件情景路径" : "基线代表路径"}
          {simulation?.simulation_id ? ` · 模拟编号 ${simulation.simulation_id.slice(0, 8)}` : ""}
        </p>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">
          代表路径是固定种子下的一条可复现推演路径，用于展示完整晋级过程，不代表唯一比赛结果。
        </p>
      </header>

      <ScenarioSlider
        selectedEventIds={selectedEventIds}
        onChange={applyEventSelection}
        disabled={!baselineSimulation || isRefreshingSimulation}
      />

      {scenarioComparison && (
        <section className="mb-4 rounded-xl border border-[var(--color-gold)]/30 bg-[var(--color-gold)]/5 p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-semibold text-[var(--color-gold)]">当前事件情景</span>
            <span className="text-[var(--color-text-muted)]">
              已应用 {scenarioComparison.events.length} 个事件，影响 {scenarioComparison.teams.length} 支球队
            </span>
            {scenarioComparison.ignoredCount > 0 && (
              <span className="text-[var(--color-accent)]">
                {scenarioComparison.ignoredCount} 个事件未生效
              </span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {scenarioComparison.teams.map((item) => (
              <span key={item.teamId} className="rounded-full bg-[var(--color-bg)] px-3 py-1 text-xs">
                {item.team?.name_cn || item.team?.name || `球队 ${item.teamId}`}
                <span className="ml-1 text-[var(--color-text-muted)]">
                  夺冠概率 {(item.probability * 100).toFixed(1)}%
                </span>
                <span className={`ml-1 ${item.deltaPoints > 0 ? "text-green-400" : item.deltaPoints < 0 ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"}`}>
                  {item.deltaPoints > 0 ? "+" : ""}{item.deltaPoints.toFixed(1)} 个百分点
                </span>
              </span>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--color-text-muted)]">
            {scenarioComparison.events.slice(0, 4).map((event) => (
              <span key={event.event_id}>· {event.title}</span>
            ))}
            {scenarioComparison.events.length > 4 && (
              <span>另有 {scenarioComparison.events.length - 4} 个事件</span>
            )}
          </div>
        </section>
      )}

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
                onClick={() => {
                  if (refreshError) void refreshSimulation();
                  else void refetchBaseline();
                }}
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
                stages={simulation?.representative_path.stages ?? null}
                eventInfluenced={simulation?.scenario.type === "EVENT"}
                onMatchClick={handleMatchClick}
              />
            </>
          )}
        </div>

        <div className="w-full xl:w-[360px] flex-shrink-0">
          <AnimatePresence mode="wait">
            {selectedMatch ? (
              <motion.div
                key={selectedMatch.match_key ?? selectedMatch.id}
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
                        resetPrediction();
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

                {predictError && (
                  <div className="bg-[var(--color-surface)] rounded-xl p-4 text-center mb-3">
                    <p className="text-sm text-[var(--color-accent)]">
                      预测请求失败：
                      {predictError instanceof Error ? predictError.message : "未知错误"}
                    </p>
                  </div>
                )}

                <AIPunditPanel
                  match={selectedMatch}
                  analysis={selectedAnalysis}
                  isLoading={isPending}
                />
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <AIPunditPanel match={null} analysis={null} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
