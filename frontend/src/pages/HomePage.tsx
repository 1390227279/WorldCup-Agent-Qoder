import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import ChampionHero from "../components/ChampionHero";
import ProbabilityBar from "../components/ProbabilityBar";
import type { Team, SimulationResult } from "../types";

export default function HomePage() {
  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: api.getTeams,
  });

  const { data: simulation } = useQuery<SimulationResult>({
    queryKey: ["simulation"],
    queryFn: api.getSimulation as () => Promise<SimulationResult>,
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <header className="mb-12 text-center">
        <h1 className="text-4xl font-bold mb-2 tracking-tight">
          🏆 2026 世界杯冠军预测
        </h1>
        <p className="text-[var(--color-text-muted)] text-lg">
          AI Agent 驱动 · Qwen 决策引擎 · 蒙特卡洛模拟验证
        </p>
      </header>

      {/* Champion Hero */}
      <section className="mb-12">
        <ChampionHero simulation={simulation} teams={teams} />
      </section>

      {/* Probability Bars */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold mb-6">夺冠概率 Top 10</h2>
        <ProbabilityBar simulation={simulation} teams={teams} />
      </section>

      {/* Quick Navigation */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Link
          to="/bracket"
          className="bg-[var(--color-surface)] rounded-xl p-6 hover:ring-2 hover:ring-[var(--color-primary)] transition-all"
        >
          <h3 className="text-xl font-semibold mb-2">🏟️ Bracket Sandbox</h3>
          <p className="text-[var(--color-text-muted)]">
            交互式淘汰赛推演 · 情景切换 · 实时重算
          </p>
        </Link>
        <Link
          to="/admin/events"
          className="bg-[var(--color-surface)] rounded-xl p-6 hover:ring-2 hover:ring-[var(--color-accent)] transition-all"
        >
          <h3 className="text-xl font-semibold mb-2">📋 事件管理</h3>
          <p className="text-[var(--color-text-muted)]">
            伤病/换帅动态注入 · Agent 自适应权重调整
          </p>
        </Link>
        <a
          href="/docs"
          target="_blank"
          className="bg-[var(--color-surface)] rounded-xl p-6 hover:ring-2 hover:ring-[var(--color-gold)] transition-all"
        >
          <h3 className="text-xl font-semibold mb-2">📖 API 文档</h3>
          <p className="text-[var(--color-text-muted)]">
            FastAPI 自动生成的 OpenAPI 接口文档
          </p>
        </a>
      </section>
    </div>
  );
}
