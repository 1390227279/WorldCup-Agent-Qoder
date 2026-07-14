import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import type { DataCollectionRun, DataCollectionStatus } from "../types";

const categoryLabels: Record<string, string> = {
  TOURNAMENT_SCENARIO: "赛事阵容", HISTORICAL_MATCHES: "历史比赛", TEAM_STRENGTH: "球队实力",
  OFFICIAL_RANKING: "官方排名", TOURNAMENT_RULES: "赛事规则",
};
const statusLabels: Record<DataCollectionStatus, string> = {
  FETCHING: "正在抓取", FETCHED: "已保存快照", PROCESSING: "正在处理", COMPLETED: "处理完成", FAILED: "失败",
};
const statusClasses: Record<DataCollectionStatus, string> = {
  FETCHING: "border-sky-400/50 text-sky-300", FETCHED: "border-[var(--color-primary)]/50 text-[var(--color-primary)]",
  PROCESSING: "border-violet-400/50 text-violet-300", COMPLETED: "border-[var(--color-secondary)]/50 text-[var(--color-secondary)]",
  FAILED: "border-[var(--color-error)]/50 text-[var(--color-error)]",
};

function formatBytes(bytes: number | null) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function DataSourcesPage() {
  const provenance = useQuery({ queryKey: ["data-sources"], queryFn: api.getDataSources, staleTime: 300000 });
  const sources = useQuery({ queryKey: ["collection-sources"], queryFn: api.getCollectionSources });
  const runs = useQuery({ queryKey: ["collection-runs"], queryFn: () => api.getCollectionRuns(30), refetchInterval: 15000 });
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const changes = useQuery({ queryKey: ["collection-changes", selectedRunId], queryFn: () => api.getCollectionChanges(selectedRunId!), enabled: selectedRunId !== null });

  const refreshRuns = async () => { await Promise.all([runs.refetch(), provenance.refetch()]); };
  const collect = async (sourceId: string) => {
    setActiveAction(`collect-${sourceId}`); setActionError(null); setActionMessage(null);
    try {
      const run = await api.collectDataSource(sourceId);
      setActionMessage(`采集完成：运行 #${run.id} 已保存原始快照，等待对应加载器处理。`);
      await refreshRuns();
    } catch (error) { setActionError(error instanceof Error ? error.message : "采集失败"); }
    finally { setActiveAction(null); }
  };
  const processRun = async (run: DataCollectionRun) => {
    setActiveAction(`process-${run.id}`); setActionError(null); setActionMessage(null);
    try {
      const result = await api.processCollectionRun(run.id);
      setActionMessage(result.message);
      await refreshRuns();
    } catch (error) { setActionError(error instanceof Error ? error.message : "处理失败"); await runs.refetch(); }
    finally { setActiveAction(null); }
  };
  const registerBaseline = async () => {
    setActiveAction("baseline"); setActionError(null); setActionMessage(null);
    try { const run = await api.registerLocalElo(); setActionMessage(`本地 ELO 基线已登记为运行 #${run.id}。`); await refreshRuns(); }
    catch (error) { setActionError(error instanceof Error ? error.message : "基线登记失败"); }
    finally { setActiveAction(null); }
  };

  return <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
    <header className="mb-6 border-b border-[var(--color-border)] pb-5">
      <span className="dashboard-label text-[var(--color-primary)]">DATA LINEAGE LEDGER</span>
      <h1 className="dashboard-title mt-2">数据来源与采集证据</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-muted)]">来源配置、原始快照和球队更新账本分层展示。人工基线只保证可复现，只有真实 GET 请求产生的运行记录才属于网络采集证据。</p>
    </header>

    {(provenance.error || sources.error || runs.error) && <div className="dashboard-card mb-4 border-[var(--color-error)]/50 p-4 text-sm text-[var(--color-error)]">数据工作台加载失败，请确认后端已经重启并包含最新路由。</div>}
    {actionMessage && <div className="mb-4 rounded-md border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 p-3 text-sm text-[var(--color-secondary)]">{actionMessage}</div>}
    {actionError && <div className="mb-4 rounded-md border border-[var(--color-error)]/40 bg-[var(--color-error)]/10 p-3 text-sm text-[var(--color-error)]">{actionError}</div>}

    {provenance.data && <section className="dashboard-card mb-5 border-[var(--color-primary)]/30 p-4">
      <div className="flex flex-wrap gap-3"><span className="rounded-full bg-[var(--color-secondary)]/15 px-3 py-1 text-sm text-[var(--color-secondary)]">{provenance.data.verified_local_sources} 项本地快照已校验</span><span className="rounded-full border border-[var(--color-border)] px-3 py-1 text-sm text-[var(--color-text-muted)]">{provenance.data.pending_network_sources} 项待联网刷新</span><span className="rounded-full border border-[var(--color-border)] px-3 py-1 font-mono text-xs text-[var(--color-text-muted)]">清单 {provenance.data.manifest_version}</span></div>
      <p className="mt-3 text-sm leading-6 text-[var(--color-text-muted)]">{provenance.data.transparency_notice}</p>
    </section>}

    <section className="dashboard-card mb-5 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-lg font-semibold text-white">数据采集与基线登记</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">网络来源只能使用后端白名单；人工基线会以独立获取方式登记，不伪装成 HTTP 请求。</p></div><div className="flex gap-2"><button type="button" disabled={activeAction !== null} onClick={() => void registerBaseline()} className="rounded-md border border-[var(--color-primary)] px-3 py-2 text-sm text-[var(--color-primary)] disabled:opacity-50">{activeAction === "baseline" ? "登记中……" : "登记本地 ELO 基线"}</button><button type="button" onClick={() => void refreshRuns()} className="rounded-md border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-muted)] hover:text-white">刷新账本</button></div></div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">{sources.data?.map((source) => <div key={source.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold text-white">{source.name}</h3><p className="mt-1 break-all text-xs text-[var(--color-text-muted)]">{source.url}</p></div><span className="rounded-full border border-sky-400/40 px-2 py-1 text-xs text-sky-300">真实 GET</span></div><button type="button" disabled={activeAction !== null} onClick={() => void collect(source.id)} className="mt-4 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-[#1c1d21] disabled:opacity-50">{activeAction === `collect-${source.id}` ? "采集中……" : "抓取并保存原始快照"}</button></div>)}</div>
    </section>

    <section className="dashboard-card mb-5 overflow-hidden">
      <div className="border-b border-[var(--color-border)] p-5"><h2 className="text-lg font-semibold text-white">采集运行账本</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">记录真实请求、快照指纹以及后续数据加载结果。</p></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-sm"><thead className="bg-[var(--color-surface-raised)] text-xs text-[var(--color-text-muted)]"><tr><th className="px-4 py-3 text-left">运行</th><th className="px-3 py-3 text-left">来源</th><th className="px-3 py-3">状态</th><th className="px-3 py-3">HTTP</th><th className="px-3 py-3">快照</th><th className="px-3 py-3">原始/更新/跳过</th><th className="px-3 py-3 text-left">SHA-256</th><th className="px-4 py-3">操作</th></tr></thead><tbody>
        {runs.data?.map((run) => <tr key={run.id} className="border-t border-[var(--color-border-muted)]"><td className="px-4 py-3"><button type="button" onClick={() => setSelectedRunId(run.id)} className="font-mono font-bold text-[var(--color-primary)] hover:underline">#{run.id}</button><p className="mt-1 text-xs text-[var(--color-text-muted)]">{new Date(run.started_at).toLocaleString("zh-CN")}</p></td><td className="px-3 py-3 text-white">{run.source_name}<p className="text-xs text-[var(--color-text-muted)]">{run.acquisition_method}</p></td><td className="px-3 py-3 text-center"><span className={`rounded-full border px-2 py-1 text-xs ${statusClasses[run.status]}`}>{statusLabels[run.status]}</span></td><td className="px-3 py-3 text-center font-mono">{run.http_status ?? "—"}</td><td className="px-3 py-3 text-center">{formatBytes(run.snapshot_bytes)}</td><td className="px-3 py-3 text-center font-mono">{run.raw_record_count} / {run.inserted_record_count || run.updated_team_count} / {run.duplicate_record_count + run.skipped_team_count}</td><td className="max-w-52 truncate px-3 py-3 font-mono text-xs text-[var(--color-text-muted)]" title={run.sha256_hash ?? ""}>{run.sha256_hash ?? "—"}</td><td className="px-4 py-3 text-center">{run.status === "FETCHED" ? <button type="button" disabled={activeAction !== null} onClick={() => void processRun(run)} className="rounded-md border border-[var(--color-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--color-primary)] disabled:opacity-50">{activeAction === `process-${run.id}` ? "处理中……" : run.source_name === "openfootball" ? "导入历史比赛" : "解析并更新球队"}</button> : <button type="button" onClick={() => setSelectedRunId(run.id)} className="text-xs text-[var(--color-text-muted)] hover:text-white">查看明细</button>}</td></tr>)}
        {!runs.isLoading && runs.data?.length === 0 && <tr><td colSpan={8} className="px-4 py-10 text-center text-[var(--color-text-muted)]">暂无真实采集运行记录</td></tr>}
      </tbody></table></div>
    </section>

    {selectedRunId !== null && <section className="dashboard-card mb-5 p-5"><div className="flex items-center justify-between"><h2 className="text-lg font-semibold text-white">运行 #{selectedRunId} 逐条变更</h2><button type="button" onClick={() => setSelectedRunId(null)} className="text-sm text-[var(--color-text-muted)] hover:text-white">关闭</button></div><div className="mt-4 space-y-2">{changes.data?.map((change) => <div key={change.id} className="grid gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-3 text-sm md:grid-cols-[120px_80px_1fr]"><span className="font-mono text-[var(--color-primary)]">{change.change_status}</span><span className="text-white">{change.fifa_code ?? change.record_type}</span><span className="text-[var(--color-text-muted)]">{change.field_name ?? change.record_type}：{change.old_value ?? "—"} → {change.new_value ?? "—"}{change.error_message ? `；${change.error_message}` : ""}</span></div>)}{!changes.isLoading && changes.data?.length === 0 && <p className="text-sm text-[var(--color-text-muted)]">该运行尚无逐条变更记录。</p>}</div></section>}

    {provenance.data && <section><div className="mb-3"><h2 className="text-lg font-semibold text-white">来源配置与本地快照</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">这里包含人工基线和公开核验入口，不等同于真实网络采集记录。</p></div><div className="grid gap-4 lg:grid-cols-2">{provenance.data.sources.map((source) => <article key={source.id} className="dashboard-card flex flex-col p-5"><div className="flex items-start justify-between gap-3"><div><span className="text-xs text-[var(--color-text-muted)]">{categoryLabels[source.category] ?? source.category} · {source.provider}</span><h3 className="mt-1 text-lg font-semibold text-white">{source.name}</h3></div><span className={`shrink-0 rounded-full border px-2 py-1 text-xs ${source.verification_status === "VERIFIED_LOCAL" ? "border-[var(--color-secondary)]/50 text-[var(--color-secondary)]" : "border-[var(--color-primary)]/50 text-[var(--color-primary)]"}`}>{source.acquisition_method === "CURATED_LOCAL_BASELINE" ? "人工基线" : source.verification_status === "VERIFIED_LOCAL" ? "本地已校验" : "待联网刷新"}</span></div><p className="mt-3 text-sm leading-6 text-[var(--color-text-muted)]">{source.notice}</p><div className="mt-4 flex flex-wrap gap-2">{source.used_by.map((item) => <span key={item} className="rounded-md bg-[var(--color-surface-raised)] px-2 py-1 text-xs text-[var(--color-text-muted)]">用于：{item}</span>)}</div>{source.snapshot_sha256 && <div className="mt-4 space-y-2 border-t border-[var(--color-border)] pt-4 text-xs"><p>记录数：{source.record_count ?? "—"}　大小：{formatBytes(source.snapshot_bytes)}</p><p className="break-all font-mono text-[var(--color-text-muted)]">SHA-256：{source.snapshot_sha256}</p></div>}{source.source_url && <a href={source.source_url} target="_blank" rel="noreferrer" className="mt-4 w-fit text-sm font-semibold text-[var(--color-primary)] hover:underline">查看公开来源 ↗</a>}</article>)}</div></section>}
  </div>;
}
