import { useState, useEffect } from "react";
import { api } from "../services/api";
import type { Event, Team } from "../types";

interface ScenarioSliderProps {
  selectedEventIds: number[];
  onChange: (ids: number[]) => void;
}

const SEVERITY_COLOR: Record<string, string> = {
  CRITICAL: "#ef4444",
  MAJOR: "#f5c518",
  MINOR: "#3b82f6",
};

export default function ScenarioSlider({ selectedEventIds, onChange }: ScenarioSliderProps) {
  const [events, setEvents] = useState<Event[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getEvents(), api.getTeams()])
      .then(([evts, tms]) => {
        setEvents(evts);
        setTeams(tms);
      })
      .finally(() => setLoading(false));
  }, []);

  const teamNameMap: Record<number, string> = {};
  for (const t of teams) {
    teamNameMap[t.id] = t.name_cn || t.name;
  }

  const activeEvents = events.filter((e) => e.active);
  const selectedSet = new Set(selectedEventIds);

  const toggleEvent = (id: number) => {
    if (selectedSet.has(id)) {
      onChange(selectedEventIds.filter((x) => x !== id));
    } else {
      onChange([...selectedEventIds, id]);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "16px 0" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: 12, color: "var(--color-text-muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
            事件影响
          </span>
          <div style={{ flex: 1, height: 1, background: "var(--color-text-muted)", opacity: 0.2 }} />
        </div>
        <p style={{ color: "var(--color-text-muted)", fontSize: 13 }}>加载事件列表…</p>
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
          事件影响
        </span>
        <div style={{ flex: 1, height: 1, background: "var(--color-text-muted)", opacity: 0.2 }} />
        {selectedEventIds.length > 0 && (
          <button
            onClick={() => onChange([])}
            style={{
              fontSize: 12,
              color: "var(--color-text-muted)",
              background: "none",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 6,
              padding: "3px 10px",
              cursor: "pointer",
            }}
          >
            重置全部
          </button>
        )}
      </div>

      {activeEvents.length === 0 ? (
        <p style={{ color: "var(--color-text-muted)", fontSize: 13 }}>暂无活跃事件</p>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {activeEvents.map((evt) => {
            const isSelected = selectedSet.has(evt.id);
            const color = SEVERITY_COLOR[evt.severity] ?? "#888";
            const teamName = evt.team_name ?? teamNameMap[evt.team_id] ?? "?";
            return (
              <button
                key={evt.id}
                onClick={() => toggleEvent(evt.id)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "5px 12px",
                  borderRadius: 20,
                  fontSize: 13,
                  cursor: "pointer",
                  transition: "all 0.15s",
                  background: isSelected ? `${color}22` : "transparent",
                  border: isSelected ? `1.5px solid ${color}` : "1.5px solid rgba(255,255,255,0.15)",
                  color: isSelected ? color : "var(--color-text-muted)",
                }}
              >
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, flexShrink: 0 }} />
                <span>{teamName}</span>
                <span style={{ opacity: 0.7, fontSize: 12 }}>{evt.title}</span>
              </button>
            );
          })}
        </div>
      )}

      <div style={{ marginTop: 10, fontSize: 12, color: "var(--color-text-muted)" }}>
        已选 <span style={{ color: "var(--color-text)", fontWeight: 600 }}>{selectedEventIds.length}</span> 个事件
      </div>
    </div>
  );
}
