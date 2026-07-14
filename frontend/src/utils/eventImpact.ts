import type { Event } from "../types";

export function resolveImpactMode(event: Event): "MATH" | "NARRATIVE" | "INVALID" {
  if (event.impact_mode) return event.impact_mode;
  const attack = event.impact?.attack_lambda_delta ?? event.impact?.attack ?? 0;
  const concede = event.impact?.concede_lambda_delta ?? event.impact?.defense ?? 0;
  return attack !== 0 || concede !== 0 ? "MATH" : "NARRATIVE";
}
