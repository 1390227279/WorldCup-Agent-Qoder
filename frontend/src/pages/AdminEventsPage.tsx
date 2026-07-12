import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Event, Team } from "../types";

const TYPE_OPTIONS = [
  { value: "INJURY", label: "伤病" },
  { value: "COACHING", label: "教练变动" },
  { value: "TACTICAL", label: "战术调整" },
  { value: "MORALE", label: "士气" },
  { value: "OTHER", label: "其他" },
];

const SEV_OPTIONS = [
  { value: "CRITICAL", label: "严重" },
  { value: "MAJOR", label: "重要" },
  { value: "MINOR", label: "一般" },
];

export default function AdminEventsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ team_id: 0, type: "INJURY", title: "", description: "", severity: "MINOR", impact: "", source: "" });

  const { data: events, isLoading } = useQuery({ queryKey: ["events"], queryFn: api.getEvents });
  const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: api.getTeams });

  const createMut = useMutation({ mutationFn: api.createEvent, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["events"] }); setShowForm(false); } });
  const toggleMut = useMutation({ mutationFn: ({ id, active }: { id: number; active: boolean }) => api.updateEvent(id, { active }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["events"] }) });
  const deleteMut = useMutation({ mutationFn: api.deleteEvent, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["events"] }) });

  const handleCreate = () => {
    let impact: Record<string, number> | undefined;
    if (form.impact.trim()) {
      try { impact = JSON.parse(form.impact); } catch { alert("影响值 JSON 格式错误"); return; }
    }
    createMut.mutate({ ...form, team_id: Number(form.team_id), impact, description: form.description || undefined, source: form.source || undefined });
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <Link to="/" className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors mb-6 inline-block">← 返回首页</Link>

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">事件管理</h1>
          <p className="text-[var(--color-text-muted)] text-sm">伤病、教练变动、战术调整等动态事件，Agent 会实时感知并调整预测权重</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm hover:opacity-90 transition-opacity">
          {showForm ? "取消" : "+ 新建事件"}
        </button>
      </div>

      {/* 创建表单 */}
      {showForm && (
        <div className="bg-[var(--color-surface)] rounded-xl p-6 mb-8 space-y-4">
          <h2 className="font-semibold text-lg">新建事件</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">球队</label>
              <select value={form.team_id} onChange={e => setForm({ ...form, team_id: Number(e.target.value) })} className="w-full bg-[var(--color-bg)] rounded-lg px-3 py-2 text-sm border border-[var(--color-text-muted)]/20">
                <option value={0}>选择球队...</option>
                {Array.isArray(teams) && teams.map((t: Team) => <option key={t.id} value={t.id}>{t.name_cn} ({t.name})</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">类型</label>
              <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })} className="w-full bg-[var(--color-bg)] rounded-lg px-3 py-2 text-sm border border-[var(--color-text-muted)]/20">
                {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">严重程度</label>
              <select value={form.severity} onChange={e => setForm({ ...form, severity: e.target.value })} className="w-full bg-[var(--color-bg)] rounded-lg px-3 py-2 text-sm border border-[var(--color-text-muted)]/20">
                {SEV_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">来源</label>
              <input value={form.source} onChange={e => setForm({ ...form, source: e.target.value })} placeholder="新闻来源（可选）" className="w-full bg-[var(--color-bg)] rounded-lg px-3 py-2 text-sm border border-[var(--color-text-muted)]/20" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">标题</label>
              <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="事件标题" className="w-full bg-[var(--color-bg)] rounded-lg px-3 py-2 text-sm border border-[var(--color-text-muted)]/20" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">描述</label>
              <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="事件详细描述（可选）" rows={2} className="w-full bg-[var(--color-bg)] rounded-lg px-3 py-2 text-sm border border-[var(--color-text-muted)]/20 resize-none" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">影响值（JSON）</label>
              <input value={form.impact} onChange={e => setForm({ ...form, impact: e.target.value })} placeholder='{"attack": -0.10, "team_morale": -0.05}' className="w-full bg-[var(--color-bg)] rounded-lg px-3 py-2 text-sm border border-[var(--color-text-muted)]/20 font-mono" />
            </div>
          </div>
          <button onClick={handleCreate} disabled={!form.team_id || !form.title || createMut.isPending} className="w-full py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm hover:opacity-90 disabled:opacity-50 transition-opacity">
            {createMut.isPending ? "创建中..." : "创建事件"}
          </button>
        </div>
      )}

      {/* 事件列表 */}
      {isLoading ? (
        <p className="text-[var(--color-text-muted)] text-center py-8">加载中...</p>
      ) : !Array.isArray(events) || events.length === 0 ? (
        <p className="text-[var(--color-text-muted)] text-center py-8">暂无事件，点击上方按钮创建</p>
      ) : (
        <div className="space-y-3">
          {events.map((event: Event) => (
            <div key={event.id} className={`bg-[var(--color-surface)] rounded-lg p-4 border-l-4 ${!event.active ? "opacity-50" : ""}`}
              style={{ borderLeftColor: event.severity === "CRITICAL" ? "#e94560" : event.severity === "MAJOR" ? "#f59e0b" : "#3b82f6" }}>
              <div className="flex justify-between items-start mb-1">
                <div>
                  <span className="text-xs text-[var(--color-text-muted)] mr-2">[{event.type_label ?? event.type}]</span>
                  <span className="mr-2 text-xs text-[var(--color-primary)]">{event.team_name}</span>
                  <span className="font-semibold">{event.title}</span>
                  {!event.active && <span className="text-xs text-[var(--color-text-muted)] ml-2">(已停用)</span>}
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: event.severity === "CRITICAL" ? "rgba(233,69,96,0.2)" : event.severity === "MAJOR" ? "rgba(245,158,11,0.2)" : "rgba(59,130,246,0.2)" }}>
                  {event.severity_label ?? event.severity}
                </span>
              </div>
              {event.description && <p className="text-sm text-[var(--color-text-muted)] mb-1">{event.description}</p>}
              {event.impact && (
                <p className="text-xs text-[var(--color-text-muted)] mb-2">
                  影响: {Object.entries(event.impact).map(([k, v]) => `${k}: ${v > 0 ? "+" : ""}${(v * 100).toFixed(0)}%`).join(" · ")}
                </p>
              )}
              <div className="flex gap-2 mt-2">
                <button onClick={() => toggleMut.mutate({ id: event.id, active: !event.active })}
                  className="text-xs px-2 py-1 rounded border border-[var(--color-text-muted)]/20 hover:bg-[var(--color-bg)] transition-colors">
                  {event.active ? "停用" : "恢复"}
                </button>
                <button onClick={() => { if (confirm("确定删除此事件？")) deleteMut.mutate(event.id); }}
                  className="text-xs px-2 py-1 rounded border border-[var(--color-accent)]/30 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 transition-colors">
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
