import { useCallback, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import BracketTree from "../components/BracketTree";
import GroupStagePanel from "../components/GroupStagePanel";
import MatchAnalysisPanel from "../components/MatchAnalysisPanel";
import ScenarioSlider from "../components/ScenarioSlider";
import TournamentReportPanel from "../components/TournamentReportPanel";
import { usePredictions } from "../hooks/usePredictions";
import { api, simulationQueryKeys } from "../services/api";
import type { Match, SimulationResult, TournamentReportResponse } from "../types";

const IGNORED_REASON_LABELS: Record<string, string> = {
  not_found: "事件不存在",
  inactive: "事件已停用",
  not_effective: "尚未到生效时间",
  expired: "事件已过期",
  team_not_in_tournament: "球队不在当前赛事",
  invalid_impact: "影响参数格式无效",
};

export default function BracketSandboxPage() {
  const [viewMode, setViewMode] = useState<"groups" | "knockout">("groups");
  const [reportOpen, setReportOpen] = useState(false);
  const [report, setReport] = useState<TournamentReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<Error | null>(null);
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

  const simulation = selectedEventIds.length > 0 ? scenarioSimulation : baselineSimulation;
  const error = baselineError ?? refreshError;
  const isFetching = isFetchingBaseline || isRefreshingSimulation;

  const closeMatch = useCallback(() => {
    setSelectedMatch(null);
    resetPrediction();
  }, [resetPrediction]);

  const applyEventSelection = async (eventIds: number[]) => {
    const normalizedIds = [...new Set(eventIds)].sort((a, b) => a - b);
    setRefreshError(null);
    if (normalizedIds.length === 0) {
      setSelectedEventIds([]);
      setScenarioSimulation(null);
      closeMatch();
      return;
    }
    if (!baselineSimulation) throw new Error("基线模拟尚未加载完成，请稍后重试");

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
    closeMatch();
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
          simulationQueryKeys.scenario(refreshedBaseline.simulation_id, selectedEventIds),
          refreshedScenario,
        );
        setScenarioSimulation(refreshedScenario);
      } else {
        setScenarioSimulation(null);
      }
      closeMatch();
    } catch (caughtError) {
      setRefreshError(caughtError instanceof Error ? caughtError : new Error("重新模拟失败"));
    } finally {
      setIsRefreshingSimulation(false);
    }
  };

  const handleMatchClick = useCallback((match: Match) => {
    setSelectedMatch(match);
    resetPrediction();
    if (simulation?.simulation_id && match.match_key) {
      predictMatch({ simulationId: simulation.simulation_id, matchKey: match.match_key });
    }
  }, [predictMatch, resetPrediction, simulation]);

  const openTournamentReport = async () => {
    if (!simulation) return;
    setReportOpen(true);
    setReportLoading(true);
    setReportError(null);
    try {
      setReport(await api.getTournamentReport(simulation.simulation_id));
    } catch (caughtError) {
      setReportError(caughtError instanceof Error ? caughtError : new Error("冠军 AI 报告生成失败"));
    } finally {
      setReportLoading(false);
    }
  };

  const scenarioComparison = useMemo(() => {
    if (!baselineSimulation || !scenarioSimulation || scenarioSimulation.scenario.type !== "EVENT") return null;
    const affectedTeamIds = [...new Set(scenarioSimulation.scenario.math_events.map((event) => event.team_id))];
    return {
      mathEvents: scenarioSimulation.scenario.math_events,
      narrativeEvents: scenarioSimulation.scenario.narrative_events,
      ignoredEvents: scenarioSimulation.scenario.ignored_events,
      teams: affectedTeamIds.map((teamId) => {
        const scenarioAdvancement = scenarioSimulation.summary.advancement_probs[teamId];
        const baselineAdvancement = baselineSimulation.summary.advancement_probs[teamId];
        const baselineProbability = baselineSimulation.summary.champion_probs_by_team_id[teamId] ?? 0;
        const scenarioProbability = scenarioSimulation.summary.champion_probs_by_team_id[teamId] ?? 0;
        return {
          teamId,
          team: scenarioAdvancement?.team ?? baselineAdvancement?.team,
          probability: scenarioProbability,
          deltaPoints: (scenarioProbability - baselineProbability) * 100,
        };
      }),
    };
  }, [baselineSimulation, scenarioSimulation]);

  const selectedAnalysis = mutationResult
    && selectedMatch?.match_key === mutationResult.match_key
    && simulation?.simulation_id === mutationResult.simulation_id
    ? mutationResult
    : null;

  return (
    <div className="mx-auto max-w-[1760px] px-3 py-4 sm:px-5 lg:px-6">
      <header className="mb-4 flex flex-wrap items-end justify-between gap-4 border-b border-[var(--color-border)] pb-4">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${simulation?.scenario.type === "EVENT" ? "bg-[var(--color-primary)] shadow-[var(--shadow-glow)]" : "bg-[var(--color-secondary)]"}`} />
            <span className="dashboard-label uppercase">赛事模拟工作台</span>
          </div>
          <h1 className="dashboard-title">淘汰赛代表路径</h1>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
            {simulation?.scenario.type === "EVENT" ? simulation.scenario.label : "基础实力基线"}
            {simulation?.simulation_id ? ` · 模拟编号 ${simulation.simulation_id.slice(0, 8)}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => void openTournamentReport()} disabled={!simulation || reportLoading} className="rounded-md border border-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-[var(--color-primary)] transition-colors hover:bg-[var(--color-primary)]/10 disabled:opacity-50">冠军 AI 报告</button>
          <span className="hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-xs text-[var(--color-text-muted)] sm:inline-block">代表路径并非唯一赛果</span>
          <button type="button" onClick={() => void refreshSimulation()} disabled={isRefreshingSimulation} className="rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-[#1c1d21] transition-colors hover:bg-[var(--color-primary-hover)] disabled:opacity-50">
            {isRefreshingSimulation ? "重新模拟中…" : "重新模拟"}
          </button>
        </div>
      </header>

      <ScenarioSlider selectedEventIds={selectedEventIds} onChange={applyEventSelection} disabled={!baselineSimulation || isRefreshingSimulation} />

      {scenarioComparison && (
        <section className="dashboard-card mb-4 border-[var(--color-primary)]/25 p-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
            <span className="font-semibold text-[var(--color-primary)]">{simulation?.scenario.label}</span>
            <span className="text-[var(--color-text-muted)]">{scenarioComparison.mathEvents.length} 项数学影响 · {scenarioComparison.narrativeEvents.length} 项 AI 背景</span>
            {scenarioComparison.teams.map((item) => (
              <span key={item.teamId} className="border-l border-[var(--color-border)] pl-4">
                {item.team?.name_cn || item.team?.name || `球队 ${item.teamId}`}
                <b className="ml-1 font-mono text-white">{(item.probability * 100).toFixed(1)}%</b>
                <i className={`ml-1 not-italic ${item.deltaPoints > 0 ? "text-[var(--color-secondary)]" : item.deltaPoints < 0 ? "text-[var(--color-error)]" : "text-[var(--color-text-muted)]"}`}>{item.deltaPoints > 0 ? "+" : ""}{item.deltaPoints.toFixed(1)} 个百分点</i>
              </span>
            ))}
          </div>
          {(scenarioComparison.mathEvents.length > 0 || scenarioComparison.narrativeEvents.length > 0) && (
            <div className="mt-2 flex flex-wrap gap-2 border-t border-[var(--color-border-muted)] pt-2 text-xs">
              {scenarioComparison.mathEvents.map((event) => <span key={event.event_id} className="rounded-md border border-[var(--color-primary)] bg-[var(--color-primary)]/10 px-2 py-1 text-[var(--color-primary)]">∑ {event.title}</span>)}
              {scenarioComparison.narrativeEvents.map((event) => <span key={event.event_id} title="仅作为 AI 解读背景，不影响数学胜率" className="rounded-md border border-dashed border-[var(--color-border)] px-2 py-1 text-[var(--color-text-muted)]">✦ {event.title}</span>)}
            </div>
          )}
          {scenarioComparison.ignoredEvents.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--color-error)]">
              {scenarioComparison.ignoredEvents.map((event) => <span key={event.event_id}>事件 #{event.event_id}：{IGNORED_REASON_LABELS[event.reason] ?? event.reason}</span>)}
            </div>
          )}
        </section>
      )}

      <div className="min-w-0">
        <section className="dashboard-card relative min-w-0 overflow-hidden p-3 sm:p-4">
          <div className="mb-4 flex items-center gap-2 border-b border-[var(--color-border)] pb-3">
            <button type="button" onClick={() => setViewMode("groups")} className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${viewMode === "groups" ? "bg-[var(--color-primary)] text-[#1c1d21]" : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-raised)] hover:text-white"}`}>小组赛预测</button>
            <button type="button" onClick={() => setViewMode("knockout")} className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${viewMode === "knockout" ? "bg-[var(--color-primary)] text-[#1c1d21]" : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-raised)] hover:text-white"}`}>淘汰赛路径</button>
            <span className="ml-auto hidden text-xs text-[var(--color-text-muted)] sm:inline">同一代表路径下的小组赛与淘汰赛结果</span>
          </div>
          {isLoading && <div className="flex min-h-[520px] items-center justify-center text-sm text-[var(--color-text-muted)]">正在加载淘汰赛数据…</div>}
          {error && (
            <div className="flex min-h-[520px] items-center justify-center text-center">
              <div>
                <p className="font-semibold text-[var(--color-error)]">对阵数据加载失败</p>
                <p className="mt-1 text-sm text-[var(--color-text-muted)]">{error instanceof Error ? error.message : "未知错误"}</p>
                <button type="button" onClick={() => refreshError ? void refreshSimulation() : void refetchBaseline()} className="mt-4 rounded-md border border-[var(--color-border)] px-4 py-2 text-sm hover:border-[var(--color-primary)]">重新加载</button>
              </div>
            </div>
          )}
          {!error && !isLoading && (
            <>
              {isFetching && <span className="absolute right-4 top-4 z-10 text-xs text-[var(--color-text-muted)]">刷新中…</span>}
              {viewMode === "groups" ? (
                <GroupStagePanel groups={simulation?.representative_path.group_stage ?? null} />
              ) : (
                <BracketTree stages={simulation?.representative_path.stages ?? null} eventInfluenced={simulation?.scenario.type === "EVENT"} selectedMatchKey={selectedMatch?.match_key ?? null} onMatchClick={handleMatchClick} />
              )}
            </>
          )}
        </section>

      </div>

      <AnimatePresence>
        {reportOpen && (
          <motion.div className="fixed inset-0 z-50 flex justify-end" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <button type="button" aria-label="关闭冠军 AI 报告" onClick={() => setReportOpen(false)} className="absolute inset-0 bg-[#0d1114]/80" />
            <motion.aside initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ duration: 0.3, ease: "easeOut" }} className="relative h-full w-full max-w-[760px] overflow-hidden border-l border-[var(--color-border)] shadow-[var(--shadow-panel)]">
              <TournamentReportPanel report={report} loading={reportLoading} error={reportError} onClose={() => setReportOpen(false)} />
            </motion.aside>
          </motion.div>
        )}
        {selectedMatch && (
          <motion.div className="fixed inset-0 z-50 flex justify-end" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <button type="button" aria-label="关闭 AI 战情面板" onClick={closeMatch} className="absolute inset-0 bg-[#0d1114]/80" />
            <motion.aside initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ duration: 0.3, ease: "easeOut" }} className="relative h-full w-full max-w-[480px] overflow-hidden border-l border-[var(--color-border)] shadow-[var(--shadow-panel)]">
              <MatchAnalysisPanel match={selectedMatch} analysis={selectedAnalysis} isLoading={isPending} error={predictError instanceof Error ? predictError : null} onClose={closeMatch} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
