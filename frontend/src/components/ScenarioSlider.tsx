import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

/* ================================================================
   Types & Data
   ================================================================ */

export interface Scenario {
  id: string;
  label: string;
  emoji: string;
  description: string;
  /** 受影响的球队及其 ELO 调整（攻击力 / 防守力偏移百分比） */
  effects: Record<string, { attack_mod: number; defense_mod: number }>;
}

export const SCENARIOS: Scenario[] = [
  {
    id: "default",
    label: "默认",
    emoji: "⚽",
    description: "所有事件按现状，无额外干预",
    effects: {},
  },
  {
    id: "mbappe-out",
    label: "姆巴佩缺阵",
    emoji: "🇫🇷",
    description: "法国核心前锋伤缺，攻击力显著下降",
    effects: { France: { attack_mod: -0.15, defense_mod: 0 } },
  },
  {
    id: "brazil-coach",
    label: "巴西换帅",
    emoji: "🇧🇷",
    description: "巴西临阵换帅，战术凝聚力下降",
    effects: { Brazil: { attack_mod: -0.08, defense_mod: -0.1 } },
  },
  {
    id: "messi-peak",
    label: "梅西巅峰",
    emoji: "🇦🇷",
    description: "梅西状态火热，阿根廷攻击力大幅上升",
    effects: { Argentina: { attack_mod: 0.18, defense_mod: 0 } },
  },
  {
    id: "england-tactics",
    label: "英格兰新战术",
    emoji: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    description: "英格兰防守反击体系增强",
    effects: { England: { attack_mod: 0.05, defense_mod: 0.12 } },
  },
];

/* ================================================================
   Component
   ================================================================ */

interface Props {
  /** 当前选中的情景 ID，默认 "default" */
  defaultId?: string;
  /** 切换情景时的回调 */
  onChange?: (scenario: Scenario) => void;
}

export default function ScenarioSlider({
  defaultId = "default",
  onChange,
}: Props) {
  const [activeId, setActiveId] = useState(defaultId);

  const handleSelect = (scenario: Scenario) => {
    setActiveId(scenario.id);
    onChange?.(scenario);
  };

  const activeScenario = SCENARIOS.find((s) => s.id === activeId) ?? SCENARIOS[0];

  return (
    <div className="mb-6">
      {/* Label */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
          情景切换
        </span>
        <div className="flex-1 h-px bg-[var(--color-text-muted)] opacity-20" />
      </div>

      {/* Scenario buttons */}
      <div className="flex flex-wrap gap-2">
        {SCENARIOS.map((scenario) => {
          const isActive = scenario.id === activeId;

          return (
            <motion.button
              key={scenario.id}
              onClick={() => handleSelect(scenario)}
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.97 }}
              className="relative rounded-lg px-4 py-2.5 text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-gold)]"
              style={{
                background: isActive
                  ? "linear-gradient(135deg, rgba(245,197,24,0.15) 0%, rgba(233,69,96,0.1) 100%)"
                  : "var(--color-surface)",
                border: isActive
                  ? "1.5px solid var(--color-gold)"
                  : "1.5px solid transparent",
                color: isActive
                  ? "var(--color-gold)"
                  : "var(--color-text-muted)",
                boxShadow: isActive
                  ? "0 0 16px rgba(245,197,24,0.12)"
                  : "none",
              }}
            >
              <span className="mr-1.5">{scenario.emoji}</span>
              {scenario.label}

              {/* Active indicator dot */}
              <AnimatePresence>
                {isActive && (
                  <motion.span
                    layoutId="scenario-indicator"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    exit={{ scale: 0 }}
                    transition={{ type: "spring", stiffness: 400, damping: 25 }}
                    className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-[var(--color-gold)]"
                  />
                )}
              </AnimatePresence>
            </motion.button>
          );
        })}
      </div>

      {/* Description with AnimatePresence */}
      <div className="mt-3 h-8 overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeId}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="flex items-center gap-2 text-sm"
          >
            <span className="text-base">{activeScenario.emoji}</span>
            <span className="text-[var(--color-text)] font-medium">
              {activeScenario.label}
            </span>
            <span className="text-[var(--color-text-muted)]">—</span>
            <span className="text-[var(--color-text-muted)]">
              {activeScenario.description}
            </span>

            {/* Affected teams badges */}
            {Object.keys(activeScenario.effects).length > 0 && (
              <span className="ml-2 flex gap-1.5">
                {Object.entries(activeScenario.effects).map(([team, fx]) => (
                  <span
                    key={team}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-mono"
                    style={{
                      background: "var(--color-bg)",
                      color:
                        fx.attack_mod > 0
                          ? "#4ade80"
                          : fx.attack_mod < 0
                            ? "#f87171"
                            : "var(--color-text-muted)",
                    }}
                  >
                    {team}
                    {fx.attack_mod !== 0 && (
                      <span>
                        ATK{fx.attack_mod > 0 ? "+" : ""}
                        {Math.round(fx.attack_mod * 100)}%
                      </span>
                    )}
                    {fx.defense_mod !== 0 && (
                      <span>
                        DEF{fx.defense_mod > 0 ? "+" : ""}
                        {Math.round(fx.defense_mod * 100)}%
                      </span>
                    )}
                  </span>
                ))}
              </span>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
