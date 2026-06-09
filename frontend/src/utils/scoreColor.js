/** Индекс проблемности: чем выше — тем больше проблем (5–100). */
export function scoreColor(score) {
  if (score == null) return '#cbd5e1'
  if (score >= 75) return '#991b1b'
  if (score >= 60) return '#ef4444'
  if (score >= 50) return '#f97316'
  if (score >= 35) return '#84cc16'
  return '#22c55e'
}
