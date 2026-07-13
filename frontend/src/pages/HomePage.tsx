import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, simulationQueryKeys } from "../services/api";
import ChampionHero from "../components/ChampionHero";
import ProbabilityBar from "../components/ProbabilityBar";
import type { SimulationResult } from "../types";

export default function HomePage() {
  const { data: simulation } = useQuery<SimulationResult>({
    queryKey: simulationQueryKeys.baseline,
    queryFn: () => api.getSimulation(),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <header className="mb-12 text-center">
        <h1 className="text-4xl font-bold mb-2 tracking-tight">
          🏆 2026 世界杯基础实力预测
        </h1>
        <p className="text-[var(--color-text-muted)] text-lg">
          基础实力基线（不含事件） · ELO 与泊松模型 · 蒙特卡洛统计
        </p>
      </header>

      {/* Champion Hero */}
      <section className="mb-12">
        <ChampionHero simulation={simulation} />
      </section>

      {/* Probability Bars */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold mb-6">夺冠概率前十名</h2>
        <ProbabilityBar simulation={simulation} />
      </section>

      {/* Quick Navigation */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link
          to="/bracket"
          className="bg-[var(--color-surface)] rounded-xl p-6 hover:ring-2 hover:ring-[var(--color-primary)] transition-all"
        >
          <h3 className="text-xl font-semibold mb-2">🏟️ 淘汰赛推演</h3>
          <p className="text-[var(--color-text-muted)]">
            交互式淘汰赛推演 · 情景切换 · 实时重算
          </p>
        </Link>
        <Link
          to="/admin/events"
          className="bg-[var(--color-surface)] rounded-xl p-6 hover:ring-2 hover:ring-[var(--color-accent)] transition-all"
        >
          <h3 className="text-xl font-semibold mb-2">📋 赛事事件管理</h3>
          <p className="text-[var(--color-text-muted)]">
            维护伤病、教练和战术事件 · 调整情景模拟
          </p>
        </Link>
      </section>
    </div>
  );
}
