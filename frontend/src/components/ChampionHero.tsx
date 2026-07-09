import { motion } from "framer-motion";
import type { Team, SimulationResult } from "../types";

interface Props {
  simulation: SimulationResult | undefined;
  teams: Team[] | undefined;
}

export default function ChampionHero({ simulation, teams }: Props) {
  if (!simulation || !teams) {
    return (
      <div className="bg-[var(--color-surface)] rounded-2xl p-12 text-center">
        <p className="text-4xl mb-4">🤖</p>
        <p className="text-xl text-[var(--color-text-muted)]">
          AI Agent 正在分析数据，生成冠军预测...
        </p>
        <p className="text-sm text-[var(--color-text-muted)] mt-2">
          启动后端服务后，此区域将展示 Agent 推演的冠军结果
        </p>
      </div>
    );
  }

  const top3 = simulation.top3 ?? [];
  if (top3.length === 0) {
    return (
      <div className="bg-[var(--color-surface)] rounded-2xl p-12 text-center">
        <p className="text-xl text-[var(--color-text-muted)]">
          预测数据加载中...
        </p>
      </div>
    );
  }

  const [championName, championProb] = top3[0];
  const champion = teams.find(
    (t) => t.name === championName || t.name_cn === championName
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="bg-[var(--color-surface)] rounded-2xl p-8 md:p-12 text-center relative overflow-hidden"
    >
      {/* Gold glow background */}
      <div
        className="absolute inset-0 opacity-10"
        style={{
          background:
            "radial-gradient(circle at center, var(--color-gold) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10">
        <p className="text-sm text-[var(--color-text-muted)] uppercase tracking-widest mb-4">
          Agent 推演 · 蒙特卡洛 {simulation.iterations?.toLocaleString() ?? "10,000"} 次模拟
        </p>

        {champion && (
          <motion.div
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.3, type: "spring", stiffness: 200 }}
          >
            <p className="text-6xl mb-3">🏆</p>
            <h2 className="text-5xl font-bold text-[var(--color-gold)] mb-2">
              {champion.name_cn}
            </h2>
            <p className="text-lg text-[var(--color-text-muted)] mb-4">
              {champion.name}
            </p>
            <div className="inline-flex items-center gap-2 bg-[var(--color-gold)]/10 rounded-full px-6 py-2">
              <span className="text-3xl font-bold text-[var(--color-gold)]">
                {(championProb * 100).toFixed(1)}%
              </span>
              <span className="text-sm text-[var(--color-text-muted)]">
                夺冠概率
              </span>
            </div>
          </motion.div>
        )}

        {/* Top 3 summary */}
        <div className="mt-8 flex justify-center gap-8 flex-wrap">
          {top3.map(([name, prob], i) => {
            const team = teams.find(
              (t) => t.name === name || t.name_cn === name
            );
            const colors = [
              "text-[var(--color-gold)]",
              "text-[var(--color-silver)]",
              "text-[var(--color-bronze)]",
            ];
            return (
              <div key={name} className="text-center">
                <p className={`text-2xl font-bold ${colors[i]}`}>
                  {(prob * 100).toFixed(1)}%
                </p>
                <p className="text-sm text-[var(--color-text-muted)]">
                  {team?.name_cn ?? name}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
