import { motion, AnimatePresence } from "framer-motion";
import type { AgentPrediction } from "../types";

/* ================================================================
   Helpers
   ================================================================ */

function confidenceColor(c: number): string {
  if (c >= 0.7) return "#4ade80";
  if (c >= 0.5) return "var(--color-gold)";
  return "var(--color-accent)";
}

function confidenceLabel(c: number): string {
  if (c >= 0.8) return "极高";
  if (c >= 0.65) return "较高";
  if (c >= 0.5) return "中等";
  return "偏低";
}

/* ================================================================
   Sub-components
   ================================================================ */

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-2 mt-5 first:mt-0">
      <span className="text-xs font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
        {children}
      </span>
      <div className="flex-1 h-px bg-[var(--color-text-muted)] opacity-15" />
    </div>
  );
}

/* ── Empty state ── */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="text-4xl mb-3 opacity-40">🤖</span>
      <p className="text-[var(--color-text-muted)] text-sm">暂无 AI 分析数据</p>
      <p className="text-[var(--color-text-muted)] text-xs mt-1 opacity-60">
        选择一场比赛后，Agent 将生成完整推理报告
      </p>
    </div>
  );
}

/* ── Degradation banner ── */
function DegradationBanner() {
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-2 rounded-lg px-3 py-2 mb-4 text-xs font-medium"
      style={{
        background: "rgba(245,197,24,0.1)",
        border: "1px solid rgba(245,197,24,0.3)",
        color: "var(--color-gold)",
      }}
    >
      <span className="text-base">⚠️</span>
      <span>Qwen Agent 不可用，当前使用泊松统计模型（降级预测）</span>
    </motion.div>
  );
}

/* ── Model badge ── */
function ModelBadge({ isAgent, model }: { isAgent: boolean; model: string | null }) {
  return (
    <div
      className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-mono"
      style={{
        background: isAgent ? "rgba(26,86,219,0.15)" : "rgba(245,197,24,0.12)",
        color: isAgent ? "var(--color-primary)" : "var(--color-gold)",
        border: `1px solid ${isAgent ? "rgba(26,86,219,0.3)" : "rgba(245,197,24,0.25)"}`,
      }}
    >
      <span>{isAgent ? "🤖" : "📊"}</span>
      {isAgent ? `${model ?? "Qwen Max"} Agent 决策` : "泊松统计模型（降级）"}
    </div>
  );
}

/* ── Prediction summary card ── */
function PredictionSummary({ prediction }: { prediction: AgentPrediction }) {
  const conf = prediction.confidence ?? 0.5;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 }}
      className="rounded-xl p-4"
      style={{
        background: "var(--color-bg)",
        border: `1px solid ${prediction.is_agent ? "var(--color-primary)" : "var(--color-gold)"}`,
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">
          预测结果
        </span>
        <ModelBadge isAgent={prediction.is_agent} model={prediction.model_used} />
      </div>

      {/* Winner */}
      <div className="flex items-end gap-4 mb-3">
        <div>
          <p className="text-xs text-[var(--color-text-muted)] mb-0.5">获胜方</p>
          <p className="text-2xl font-bold text-[var(--color-text)]">
            {prediction.winner ?? "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-[var(--color-text-muted)] mb-0.5">预测比分</p>
          <p className="text-2xl font-bold font-mono text-[var(--color-accent)]">
            {prediction.predicted_score ?? "—"}
          </p>
        </div>
      </div>

      {/* Confidence bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-[var(--color-text-muted)]">
            置信度 · {confidenceLabel(conf)}
          </span>
          <span
            className="text-sm font-bold font-mono"
            style={{ color: confidenceColor(conf) }}
          >
            {(conf * 100).toFixed(0)}%
          </span>
        </div>
        <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--color-surface)" }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.max(conf * 100, 2)}%` }}
            transition={{ delay: 0.2, duration: 0.6, ease: "easeOut" }}
            className="h-full rounded-full"
            style={{
              background: `linear-gradient(90deg, var(--color-primary), ${confidenceColor(conf)})`,
            }}
          />
        </div>
      </div>
    </motion.div>
  );
}

/* ── Key factors list ── */
function KeyFactorsList({ factors }: { factors: string[] }) {
  return (
    <div className="space-y-1.5">
      <AnimatePresence>
        {factors.map((factor, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 + i * 0.06 }}
            className="flex items-start gap-2.5 text-sm"
          >
            <span
              className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5"
              style={{
                background: "var(--color-primary)",
                color: "#fff",
              }}
            >
              {i + 1}
            </span>
            <span className="text-[var(--color-text)] leading-relaxed">{factor}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

/* ── Reasoning chain ── */
function ReasoningChainView({
  chain,
}: {
  chain: AgentPrediction["reasoning_chain"];
}) {
  if (!chain || chain.length === 0) {
    return (
      <p className="text-xs text-[var(--color-text-muted)] italic">
        推理链数据为空
      </p>
    );
  }

  return (
    <div className="relative">
      {/* Vertical timeline line */}
      <div
        className="absolute left-[11px] top-2 bottom-2 w-px"
        style={{ background: "var(--color-text-muted)", opacity: 0.2 }}
      />

      <div className="space-y-3">
        {chain.map((step, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.08 }}
            className="relative pl-8"
          >
            {/* Timeline dot */}
            <div
              className="absolute left-[5px] top-1 w-[13px] h-[13px] rounded-full border-2"
              style={{
                borderColor: "var(--color-primary)",
                background: "var(--color-bg)",
              }}
            />

            {/* Step header */}
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold text-[var(--color-primary)]">
                Step {step.step ?? i + 1}
              </span>
              {step.tool && (
                <span
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                  style={{
                    background: "rgba(26,86,219,0.12)",
                    color: "var(--color-primary)",
                  }}
                >
                  {step.tool}
                </span>
              )}
            </div>

            {/* Finding */}
            {step.finding && (
              <p className="text-sm text-[var(--color-text)] leading-relaxed mb-0.5">
                {step.finding}
              </p>
            )}

            {/* Analysis */}
            {step.analysis && (
              <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">
                💡 {step.analysis}
              </p>
            )}

            {/* Conclusion */}
            {step.conclusion && (
              <p className="text-xs mt-1 font-medium" style={{ color: "var(--color-gold)" }}>
                → {step.conclusion}
              </p>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
}

/* ── Tool calls log ── */
function ToolCallsLog({
  calls,
}: {
  calls: AgentPrediction["tool_calls_log"];
}) {
  if (!calls || calls.length === 0) return null;

  return (
    <div className="space-y-1.5">
      {calls.map((tc, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 + i * 0.04 }}
          className="flex items-center gap-2 text-xs font-mono rounded-md px-2.5 py-1.5"
          style={{ background: "var(--color-bg)" }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{
              background: tc.success ? "#4ade80" : "var(--color-accent)",
            }}
          />
          <span className="text-[var(--color-text)]">{tc.tool_name}</span>
          <span className="text-[var(--color-text-muted)] ml-auto">
            {tc.execution_time_ms}ms
          </span>
        </motion.div>
      ))}
    </div>
  );
}

/* ================================================================
   Main Component
   ================================================================ */

interface Props {
  prediction: AgentPrediction | null;
}

export default function AIPunditPanel({ prediction }: Props) {
  if (!prediction) {
    return (
      <div className="bg-[var(--color-surface)] rounded-xl p-4">
        <EmptyState />
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="bg-[var(--color-surface)] rounded-xl p-5"
      style={{
        border: prediction.is_agent
          ? "none"
          : "1px solid rgba(245,197,24,0.25)",
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-lg">🧠</span>
        <h3 className="text-sm font-bold text-[var(--color-text)]">
          AI 评论员分析
        </h3>
      </div>

      {/* Degradation warning */}
      {!prediction.is_agent && <DegradationBanner />}

      {/* Prediction summary */}
      <PredictionSummary prediction={prediction} />

      {/* Key factors */}
      {prediction.key_factors && prediction.key_factors.length > 0 && (
        <>
          <SectionTitle>关键因素</SectionTitle>
          <KeyFactorsList factors={prediction.key_factors} />
        </>
      )}

      {/* Reasoning chain */}
      {prediction.reasoning_chain && prediction.reasoning_chain.length > 0 && (
        <>
          <SectionTitle>推理链</SectionTitle>
          <ReasoningChainView chain={prediction.reasoning_chain} />
        </>
      )}

      {/* Tool calls log */}
      {prediction.tool_calls_log && prediction.tool_calls_log.length > 0 && (
        <>
          <SectionTitle>工具调用记录</SectionTitle>
          <ToolCallsLog calls={prediction.tool_calls_log} />
        </>
      )}
    </motion.div>
  );
}
