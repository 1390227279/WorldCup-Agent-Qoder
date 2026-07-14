import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import EventImpactBadge from "../components/EventImpactBadge";
import type { Event, EventCreate, EventImportResult, EventUpdate, Team } from "../types";

const TYPE_OPTIONS = [
  { value: "INJURY", label: "伤病" },
  { value: "COACHING", label: "教练变动" },
  { value: "TACTICAL", label: "战术调整" },
  { value: "MORALE", label: "士气" },
  { value: "OTHER", label: "其他" },
];

const SEVERITY_OPTIONS = [
  { value: "CRITICAL", label: "严重" },
  { value: "MAJOR", label: "重要" },
  { value: "MINOR", label: "一般" },
];

const SOURCE_TYPE_OPTIONS = [
  { value: "MANUAL", label: "人工维护" },
  { value: "NEWS", label: "新闻来源" },
  { value: "API", label: "数据接口" },
  { value: "IMPORT", label: "批量导入" },
];

interface EventFormState {
  team_id: number;
  type: string;
  title: string;
  description: string;
  severity: string;
  impact_mode: "MATH" | "NARRATIVE";
  attack_percent: string;
  concede_percent: string;
  other_impact: Record<string, number>;
  source: string;
  source_type: string;
  source_url: string;
  external_id: string;
  effective_at: string;
  expires_at: string;
}

function emptyForm(): EventFormState {
  return {
    team_id: 0,
    type: "INJURY",
    title: "",
    description: "",
    severity: "MINOR",
    impact_mode: "MATH",
    attack_percent: "0",
    concede_percent: "0",
    other_impact: {},
    source: "",
    source_type: "MANUAL",
    source_url: "",
    external_id: "",
    effective_at: "",
    expires_at: "",
  };
}

function datetimeInputValue(value?: string | null): string {
  return value ? value.slice(0, 16) : "";
}

function percentFromImpact(event: Event, canonical: string, legacy: string): string {
  const value = event.impact?.[canonical] ?? event.impact?.[legacy] ?? 0;
  return String(Number((value * 100).toFixed(2)));
}

function otherImpactFields(event: Event): Record<string, number> {
  return Object.fromEntries(
    Object.entries(event.impact ?? {}).filter(([key]) => ![
      "attack_lambda_delta",
      "concede_lambda_delta",
      "attack",
      "defense",
    ].includes(key)),
  );
}

function formatDate(value?: string | null): string {
  if (!value) return "未设置";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function sourceTypeLabel(value?: string): string {
  return SOURCE_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? value ?? "未标注";
}

function statusClass(status?: Event["status"]): string {
  if (status === "ACTIVE") return "border-[var(--color-secondary)]/30 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]";
  if (status === "SCHEDULED") return "border-[var(--color-accent)]/30 bg-[var(--color-accent)]/10 text-[var(--color-accent)]";
  if (status === "EXPIRED") return "border-[var(--color-primary)]/30 bg-[var(--color-primary)]/10 text-[var(--color-primary)]";
  return "border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text-muted)]";
}

export default function AdminEventsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<EventFormState>(emptyForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<EventImportResult | null>(null);

  const { data: events, isLoading } = useQuery({
    queryKey: ["events", "admin"],
    queryFn: () => api.getEvents(),
  });
  const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: api.getTeams });
  const { data: metadata } = useQuery({
    queryKey: ["event-metadata"],
    queryFn: api.getEventTypes,
  });

  const invalidateEventData = async () => {
    await queryClient.invalidateQueries({ queryKey: ["events"] });
    queryClient.removeQueries({ queryKey: ["simulation", "scenario"] });
  };
  const finishSave = async () => {
    await invalidateEventData();
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm());
    setFormError(null);
  };

  const createMutation = useMutation({ mutationFn: api.createEvent, onSuccess: finishSave });
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: EventUpdate }) => api.updateEvent(id, payload),
    onSuccess: finishSave,
  });
  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => api.updateEvent(id, { active }),
    onSuccess: invalidateEventData,
  });
  const deleteMutation = useMutation({ mutationFn: api.deleteEvent, onSuccess: invalidateEventData });
  const importMutation = useMutation({
    mutationFn: api.importEvents,
    onSuccess: async (result) => {
      setImportResult(result);
      await invalidateEventData();
    },
  });

  const maxPercent = (metadata?.impact_range.max ?? 0.5) * 100;
  const minPercent = (metadata?.impact_range.min ?? -0.5) * 100;
  const saving = createMutation.isPending || updateMutation.isPending;
  const mutationError = createMutation.error ?? updateMutation.error;

  const startCreate = () => {
    setForm(emptyForm());
    setEditingId(null);
    setFormError(null);
    setShowForm(true);
  };

  const startEdit = (event: Event) => {
    setForm({
      team_id: event.team_id,
      type: event.type,
      title: event.title,
      description: event.description ?? "",
      severity: event.severity,
      impact_mode: event.impact_mode === "MATH" ? "MATH" : "NARRATIVE",
      attack_percent: percentFromImpact(event, "attack_lambda_delta", "attack"),
      concede_percent: percentFromImpact(event, "concede_lambda_delta", "defense"),
      other_impact: otherImpactFields(event),
      source: event.source ?? "",
      source_type: event.source_type ?? "MANUAL",
      source_url: event.source_url ?? "",
      external_id: event.external_id ?? "",
      effective_at: datetimeInputValue(event.effective_at),
      expires_at: datetimeInputValue(event.expires_at),
    });
    setEditingId(event.id);
    setFormError(null);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSave = () => {
    setFormError(null);
    const attackPercent = Number(form.attack_percent);
    const concedePercent = Number(form.concede_percent);
    if (!form.team_id || !form.title.trim()) {
      setFormError("请选择球队并填写事件标题");
      return;
    }
    if (
      form.impact_mode === "MATH" && (
      !Number.isFinite(attackPercent) ||
      !Number.isFinite(concedePercent) ||
      attackPercent < minPercent || attackPercent > maxPercent ||
      concedePercent < minPercent || concedePercent > maxPercent
      )
    ) {
      setFormError(`两项修正必须在 ${minPercent}% 到 +${maxPercent}% 之间`);
      return;
    }
    if (form.impact_mode === "MATH" && attackPercent === 0 && concedePercent === 0) {
      setFormError("数学影响事件必须至少填写一项非零进球期望修正");
      return;
    }
    if (
      form.effective_at &&
      form.expires_at &&
      new Date(form.expires_at) <= new Date(form.effective_at)
    ) {
      setFormError("失效时间必须晚于生效时间");
      return;
    }

    const impact = form.impact_mode === "MATH"
      ? {
          ...form.other_impact,
          attack_lambda_delta: attackPercent / 100,
          concede_lambda_delta: concedePercent / 100,
        }
      : form.other_impact;
    const createPayload: EventCreate = {
      team_id: form.team_id,
      type: form.type,
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      severity: form.severity,
      impact,
      impact_mode: form.impact_mode,
      source: form.source.trim() || undefined,
      source_type: form.source_type,
      source_url: form.source_url.trim() || undefined,
      external_id: form.external_id.trim() || undefined,
      effective_at: form.effective_at || undefined,
      expires_at: form.expires_at || undefined,
    };
    if (editingId != null) {
      updateMutation.mutate({
        id: editingId,
        payload: {
          ...createPayload,
          description: form.description.trim() || null,
          source: form.source.trim() || null,
          source_url: form.source_url.trim() || null,
          external_id: form.external_id.trim() || null,
          effective_at: form.effective_at || null,
          expires_at: form.expires_at || null,
        },
      });
    } else {
      createMutation.mutate(createPayload);
    }
  };

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-[var(--color-border)] pb-5">
        <div>
          <Link to="/" className="dashboard-label transition-colors hover:text-white">预测总览 / 变量管理</Link>
          <h1 className="dashboard-title mt-3">赛事事件管理</h1>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">区分数学概率变量与 AI 叙事背景，所有修改只作用于指定情景。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={api.eventImportTemplateUrl} className="rounded-md border border-[var(--color-border)] px-3 py-2 text-sm transition-colors hover:border-[var(--color-primary)]">下载导入模板</a>
          <label className="cursor-pointer rounded-md border border-[var(--color-border)] px-3 py-2 text-sm transition-colors hover:border-[var(--color-primary)]">
            {importMutation.isPending ? "导入中…" : "导入 CSV/JSON"}
            <input
              type="file"
              accept=".csv,.json"
              className="hidden"
              disabled={importMutation.isPending}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) importMutation.mutate(file);
                event.target.value = "";
              }}
            />
          </label>
          <button onClick={startCreate} className="rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-[#1c1d21] hover:bg-[var(--color-primary-hover)]">新建事件</button>
        </div>
      </div>

      {importResult && (
        <div className="dashboard-card mb-6 border-l-2 border-l-[var(--color-secondary)] p-4 text-sm">
          <p className="font-semibold">导入完成：共 {importResult.total} 条</p>
          <p className="text-[var(--color-text-muted)]">新增 {importResult.created} · 更新 {importResult.updated} · 跳过 {importResult.skipped} · 失败 {importResult.failed}</p>
          {importResult.errors.map((error) => <p key={`${error.row}-${error.error}`} className="mt-1 text-xs text-[var(--color-accent)]">第 {error.row} 行：{error.error}</p>)}
        </div>
      )}

      {showForm && (
        <div className="dashboard-card mb-8 space-y-5 border-[var(--color-primary)]/20 p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <div><p className="dashboard-label uppercase">事件编辑器</p><h2 className="mt-1 text-lg font-semibold">{editingId == null ? "新建事件" : "修改事件"}</h2></div>
            <button onClick={() => setShowForm(false)} className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-text-muted)] hover:text-white">取消</button>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="text-xs text-[var(--color-text-muted)]">球队
              <select value={form.team_id} onChange={(event) => setForm({ ...form, team_id: Number(event.target.value) })} className="mt-1 w-full rounded-lg border border-white/10 bg-[var(--color-bg)] px-3 py-2 text-sm">
                <option value={0}>选择球队…</option>
                {teams?.map((team: Team) => <option key={team.id} value={team.id}>{team.name_cn}</option>)}
              </select>
            </label>
            <label className="text-xs text-[var(--color-text-muted)]">事件类型
              <select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-[var(--color-bg)] px-3 py-2 text-sm">
                {TYPE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label className="text-xs text-[var(--color-text-muted)]">严重程度
              <select value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-[var(--color-bg)] px-3 py-2 text-sm">
                {SEVERITY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label className="text-xs text-[var(--color-text-muted)]">来源类型
              <select value={form.source_type} onChange={(event) => setForm({ ...form, source_type: event.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-[var(--color-bg)] px-3 py-2 text-sm">
                {SOURCE_TYPE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label className="text-xs text-[var(--color-text-muted)] md:col-span-2">标题
              <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-[var(--color-bg)] px-3 py-2 text-sm" />
            </label>
            <label className="text-xs text-[var(--color-text-muted)] md:col-span-2">描述
              <textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={2} className="mt-1 w-full resize-none rounded-lg border border-white/10 bg-[var(--color-bg)] px-3 py-2 text-sm" />
            </label>

            <div className="md:col-span-2">
              <p className="mb-2 text-xs text-[var(--color-text-muted)]">事件作用</p>
              <div className="grid gap-3 md:grid-cols-2">
                <button type="button" onClick={() => setForm({ ...form, impact_mode: "MATH" })} className={`rounded-xl border p-4 text-left ${form.impact_mode === "MATH" ? "border-[var(--color-gold)] bg-[var(--color-gold)]/15 shadow-[0_0_18px_rgba(245,158,11,0.18)]" : "border-[var(--color-gold)]/20 bg-transparent"}`}>
                  <p className="font-semibold text-[var(--color-gold)]">∑ 影响数学模型</p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">修正进球期望，并改变比赛胜率与晋级概率。</p>
                </button>
                <button type="button" onClick={() => setForm({ ...form, impact_mode: "NARRATIVE" })} className={`rounded-xl border border-dashed p-4 text-left ${form.impact_mode === "NARRATIVE" ? "border-white/50 bg-white/5" : "border-white/20 bg-transparent"}`}>
                  <p className="font-semibold">✦ 仅作为 AI 解读背景</p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">保留士气、经历和战术语境，不影响数学胜率模型。</p>
                </button>
              </div>
            </div>

            {form.impact_mode === "MATH" && (
              <>
                <div className="rounded-lg border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/5 p-3">
                  <label className="text-xs font-semibold text-[var(--color-primary)]">本队进球期望修正（%）
                    <input type="number" min={minPercent} max={maxPercent} step="1" value={form.attack_percent} onChange={(event) => setForm({ ...form, attack_percent: event.target.value })} className="mt-1 w-full rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm" />
                  </label>
                  <p className="mt-2 text-[11px] text-[var(--color-text-muted)]">例如 -10% 表示本队进球 λ × 0.90；+10% 表示 λ × 1.10。</p>
                </div>
                <div className="rounded-lg border border-[var(--color-gold)]/30 bg-[var(--color-gold)]/5 p-3">
                  <label className="text-xs font-semibold text-[var(--color-gold)]">本队失球期望修正（%）
                    <input type="number" min={minPercent} max={maxPercent} step="1" value={form.concede_percent} onChange={(event) => setForm({ ...form, concede_percent: event.target.value })} className="mt-1 w-full rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm" />
                  </label>
                  <p className="mt-2 text-[11px] text-[var(--color-text-muted)]">例如 +10% 表示对手面对本队时进球 λ × 1.10，即本队防守变差。</p>
                </div>
              </>
            )}

            <label className="text-xs text-[var(--color-text-muted)]">生效时间
              <input type="datetime-local" value={form.effective_at} onChange={(event) => setForm({ ...form, effective_at: event.target.value })} className="mt-1 w-full rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm" />
            </label>
            <label className="text-xs text-[var(--color-text-muted)]">失效时间
              <input type="datetime-local" value={form.expires_at} onChange={(event) => setForm({ ...form, expires_at: event.target.value })} className="mt-1 w-full rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm" />
            </label>
            <label className="text-xs text-[var(--color-text-muted)]">来源名称
              <input value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })} className="mt-1 w-full rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm" placeholder="公告、媒体或数据提供方" />
            </label>
            <label className="text-xs text-[var(--color-text-muted)]">来源链接
              <input value={form.source_url} onChange={(event) => setForm({ ...form, source_url: event.target.value })} className="mt-1 w-full rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm" placeholder="https://…" />
            </label>
            <label className="text-xs text-[var(--color-text-muted)] md:col-span-2">外部事件编号
              <input value={form.external_id} onChange={(event) => setForm({ ...form, external_id: event.target.value })} className="mt-1 w-full rounded-lg bg-[var(--color-bg)] px-3 py-2 text-sm" placeholder="用于导入去重（可选）" />
            </label>
          </div>
          {(formError || mutationError) && <p className="text-sm text-[var(--color-error)]">{formError || (mutationError instanceof Error ? mutationError.message : "保存失败")}</p>}
          <div className="flex justify-end border-t border-[var(--color-border)] pt-4">
            <button onClick={handleSave} disabled={saving} className="min-w-40 rounded-md bg-[var(--color-primary)] px-5 py-2 text-sm font-semibold text-[#1c1d21] hover:bg-[var(--color-primary-hover)] disabled:opacity-50">{saving ? "保存中…" : "保存事件"}</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="py-8 text-center text-[var(--color-text-muted)]">加载中…</p>
      ) : !events?.length ? (
        <p className="py-8 text-center text-[var(--color-text-muted)]">暂无事件</p>
      ) : (
        <div className="space-y-3">
          {events.map((event: Event) => {
            const attack = event.impact?.attack_lambda_delta ?? event.impact?.attack;
            const concede = event.impact?.concede_lambda_delta ?? event.impact?.defense;
            return (
              <div key={event.id} className="dashboard-card border-l-2 p-4" style={{ borderLeftColor: event.severity === "CRITICAL" ? "var(--color-error)" : event.severity === "MAJOR" ? "var(--color-primary)" : "var(--color-accent)" }}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-[var(--color-text-muted)]">[{event.type_label ?? event.type}]</span>
                      <span className="text-xs text-[var(--color-primary)]">{event.team_name}</span>
                      <span className="font-semibold">{event.title}</span>
                      <EventImpactBadge event={event} />
                      <span className={`rounded-md border px-2 py-0.5 text-xs ${statusClass(event.status)}`}>{event.status_label ?? (event.active ? "生效中" : "已停用")}</span>
                    </div>
                    <p className="mt-1 text-xs text-[var(--color-text-muted)]">所属赛事：{event.tournament?.name_cn ?? "未关联赛事"} · 严重程度：{event.severity_label ?? event.severity}</p>
                  </div>
                </div>
                {event.description && <p className="mt-2 text-sm text-[var(--color-text-muted)]">{event.description}</p>}
                {event.impact_mode === "MATH" ? (
                  <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
                    <div className="rounded-lg bg-[var(--color-bg)] p-2">本队进球期望：{attack == null ? "未设置" : `${attack >= 0 ? "+" : ""}${(attack * 100).toFixed(1)}%`}</div>
                    <div className="rounded-lg bg-[var(--color-bg)] p-2">本队失球期望：{concede == null ? "未设置" : `${concede >= 0 ? "+" : ""}${(concede * 100).toFixed(1)}%`}</div>
                  </div>
                ) : (
                  <p className="mt-3 rounded-lg border border-dashed border-white/20 px-3 py-2 text-xs text-[var(--color-text-muted)]">此事件仅作为相关比赛的 AI 解读背景，不修改比分、胜率或晋级概率。</p>
                )}
                {event.needs_impact_migration && (
                  <p className="mt-2 rounded-lg bg-orange-500/10 px-3 py-2 text-xs text-orange-300">此事件仍使用旧影响字段（{event.legacy_impact_fields?.join("、")}），点击“修改”并保存即可迁移为标准 λ 字段。</p>
                )}
                <div className="mt-3 text-xs text-[var(--color-text-muted)]">
                  <p>有效期：{formatDate(event.effective_at)} 至 {formatDate(event.expires_at)}</p>
                  <p>来源：{sourceTypeLabel(event.source_type)} · {event.source || "未填写来源"}{event.source_url && <> · <a href={event.source_url} target="_blank" rel="noreferrer" className="text-[var(--color-primary)]">查看来源</a></>}</p>
                </div>
                <div className="mt-3 flex gap-2">
                  <button onClick={() => startEdit(event)} className="rounded-md border border-[var(--color-border)] px-2.5 py-1 text-xs hover:border-[var(--color-primary)]">修改</button>
                  <button onClick={() => toggleMutation.mutate({ id: event.id, active: !event.active })} className="rounded-md border border-[var(--color-border)] px-2.5 py-1 text-xs hover:border-[var(--color-primary)]">{event.active ? "停用" : "恢复"}</button>
                  <button onClick={() => { if (confirm("确定删除此事件？")) deleteMutation.mutate(event.id); }} className="rounded-md border border-[var(--color-error)]/30 px-2.5 py-1 text-xs text-[var(--color-error)]">删除</button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
