import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, simulationQueryKeys } from "../services/api";
import ChampionHero from "../components/ChampionHero";
import ProbabilityBar from "../components/ProbabilityBar";
import type { SimulationResult } from "../types";

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="border-b border-[var(--color-border-muted)] py-3 last:border-0">
      <p className="dashboard-label">{label}</p>
      <p className="mt-1 font-mono text-base font-semibold text-white">{value}</p>
      {note && <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">{note}</p>}
    </div>
  );
}

export default function HomePage() {
  const { data: simulation, isLoading, error, refetch } = useQuery<SimulationResult>({
    queryKey: simulationQueryKeys.baseline,
    queryFn: () => api.getSimulation(),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-[var(--color-border)] pb-5">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[var(--color-secondary)] shadow-[0_0_8px_rgba(74,222,128,0.55)]" />
            <span className="dashboard-label uppercase">基础实力监测在线</span>
          </div>
          <h1 className="dashboard-title">2026 世界杯预测指挥台</h1>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">无事件基线 · ELO 与泊松模型 · 完整赛事蒙特卡洛统计</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
          <span className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5">{simulation?.tournament.status === "OFFICIAL" ? "官方赛事" : "情景赛事数据"}</span>
          <span className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 font-mono">ID {simulation?.simulation_id.slice(0, 8) ?? "--------"}</span>
        </div>
      </header>

      {error ? (
        <div className="dashboard-card p-10 text-center">
          <p className="font-semibold text-[var(--color-error)]">基线数据加载失败</p>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">{error instanceof Error ? error.message : "未知错误"}</p>
          <button onClick={() => void refetch()} className="mt-4 rounded-md bg-[var(--color-primary)] px-4 py-2 font-semibold text-[#1c1d21] transition-colors hover:bg-[var(--color-primary-hover)]">重新加载</button>
        </div>
      ) : (
        <>
          <ChampionHero simulation={isLoading ? undefined : simulation} />

          <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
            <section className="dashboard-card min-w-0 p-5 sm:p-6">
              <div className="mb-4 flex items-center justify-between border-b border-[var(--color-border)] pb-4">
                <div>
                  <p className="dashboard-label uppercase">冠军概率排行</p>
                  <h2 className="mt-1 text-base font-semibold">基础实力前十名</h2>
                </div>
                <span className="text-xs text-[var(--color-text-muted)]">点击球队查看详情</span>
              </div>
              <ProbabilityBar simulation={simulation} />
            </section>

            <aside className="space-y-5">
              <section className="dashboard-card p-5">
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="text-base font-semibold">模型状态</h2>
                  <span className="rounded-sm bg-[var(--color-secondary)]/10 px-2 py-0.5 text-xs text-[var(--color-secondary)]">稳定</span>
                </div>
                <Metric label="模拟次数" value={simulation?.model.iterations.toLocaleString() ?? "—"} note="完整赛事迭代" />
                <Metric label="主种子" value={simulation?.model.seed.toString() ?? "—"} note="普通刷新保持不变" />
                <Metric label="模型版本" value={simulation?.model.version ?? "—"} />
                <Metric label="赛事规则" value={simulation?.tournament.rules_version ?? "—"} />
                <Metric label="数据版本" value={simulation?.tournament.data_version ?? "—"} />
              </section>

              <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                <Link to="/bracket" className="dashboard-card group border-[var(--color-primary)]/20 p-5 transition-all duration-150 hover:border-[var(--color-primary)] hover:shadow-[var(--shadow-glow)]">
                  <p className="dashboard-label uppercase text-[var(--color-primary)]">赛事沙盘</p>
                  <h3 className="mt-2 font-semibold">打开淘汰赛推演</h3>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">查看完整代表路径并注入事件情景</p>
                  <p className="mt-4 text-sm text-[var(--color-primary)]">进入工作台 →</p>
                </Link>
                <Link to="/admin/events" className="dashboard-card group p-5 transition-all duration-150 hover:border-[var(--color-accent)]">
                  <p className="dashboard-label uppercase text-[var(--color-accent)]">变量管理</p>
                  <h3 className="mt-2 font-semibold">维护赛事事件</h3>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">管理数学影响和 AI 叙事背景</p>
                  <p className="mt-4 text-sm text-[var(--color-accent)]">进入管理页 →</p>
                </Link>
              </section>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
