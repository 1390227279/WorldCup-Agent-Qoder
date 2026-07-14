import type { TournamentReportResponse } from "../types";

function ReportList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section>
      <h3 className="dashboard-label mb-2 text-[var(--color-primary)]">{title}</h3>
      <ul className="space-y-2 text-sm leading-6 text-[var(--color-text-muted)]">
        {items.map((item, index) => <li key={`${title}-${index}`} className="rounded-md border border-[var(--color-border-muted)] bg-[var(--color-surface-raised)] px-3 py-2">{item}</li>)}
      </ul>
    </section>
  );
}

export default function TournamentReportPanel({ report, loading, error, onClose }: {
  report: TournamentReportResponse | null;
  loading: boolean;
  error: Error | null;
  onClose: () => void;
}) {
  return (
    <div className="flex h-full flex-col bg-[var(--color-bg)]">
      <header className="flex items-start justify-between border-b border-[var(--color-border)] p-5">
        <div><span className="dashboard-label text-[var(--color-primary)]">QWEN 冠军推演</span><h2 className="mt-1 text-xl font-bold text-white">完整冠军 AI 推理报告</h2></div>
        <button type="button" onClick={onClose} className="rounded-md border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-muted)] hover:text-white">关闭</button>
      </header>
      <div className="flex-1 overflow-y-auto p-5">
        {loading && <div className="flex min-h-80 items-center justify-center text-sm text-[var(--color-text-muted)]">Qwen 正在阅读完整赛事路径并生成中文报告……</div>}
        {error && <div className="rounded-md border border-[var(--color-error)]/50 bg-[var(--color-error)]/10 p-4 text-sm text-[var(--color-error)]">{error.message}</div>}
        {report && (
          <div className="space-y-6">
            <section className="rounded-lg border border-[var(--color-primary)]/40 bg-[var(--color-primary)]/10 p-4">
              <p className="text-xs text-[var(--color-text-muted)]">数学代表路径冠军</p>
              <div className="mt-1 flex flex-wrap items-end gap-3"><strong className="text-2xl text-[var(--color-primary)]">{report.math.champion.name_cn || report.math.champion.name}</strong><span className="font-mono text-white">决赛 {report.math.final_score}</span></div>
              <p className="mt-3 text-sm leading-7 text-white">{report.agent.champion_summary || report.agent.message}</p>
            </section>
            {report.agent.status === "agent_unavailable" && <p className="rounded-md border border-[var(--color-error)]/40 p-3 text-sm text-[var(--color-error)]">{report.agent.message}</p>}
            <ReportList title="小组赛晋级分析" items={report.agent.group_stage_reasoning} />
            <ReportList title="淘汰赛逐轮推演" items={report.agent.knockout_reasoning} />
            {report.agent.final_reasoning && <section><h3 className="dashboard-label mb-2 text-[var(--color-primary)]">决赛判断</h3><p className="text-sm leading-7 text-[var(--color-text-muted)]">{report.agent.final_reasoning}</p></section>}
            <ReportList title="关键夺冠因素" items={report.agent.key_factors} />
            <ReportList title="事件影响解释" items={report.agent.event_analysis} />
            <ReportList title="可能的替代结果" items={report.agent.alternative_outcomes} />
            <ReportList title="风险与模型边界" items={report.agent.risk_notes} />
            {report.agent.reasoning_chain.length > 0 && <section><h3 className="dashboard-label mb-3 text-[var(--color-primary)]">推理链</h3><div className="space-y-3">{report.agent.reasoning_chain.map((step) => <div key={step.step_number} className="grid grid-cols-[36px_1fr] gap-3"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-primary)] font-mono font-bold text-[#1c1d21]">{step.step_number}</span><div><p className="text-sm font-semibold text-white">{step.finding}</p>{step.analysis && <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">{step.analysis}</p>}</div></div>)}</div></section>}
            <p className="border-t border-[var(--color-border)] pt-4 text-xs text-[var(--color-text-muted)]">AI 只解释后端 ELO、泊松模型与蒙特卡洛模拟生成的既有事实，不会修改比分、胜者和概率。</p>
          </div>
        )}
      </div>
    </div>
  );
}
