/** Форматирование периода обращений для дашборда */

export function formatDateRu(value) {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

export function formatPeriod(start, end) {
  const from = formatDateRu(start)
  const to = formatDateRu(end)
  if (from && to) return from === to ? from : `${from} — ${to}`
  return from || to || null
}

export function formatIncidentStats({ totalIncidents, problemCount }) {
  const total = Number(totalIncidents)
  const problems = Number(problemCount)
  if (!Number.isFinite(total) || total <= 0) return null
  if (Number.isFinite(problems) && problems > 0 && problems !== total) {
    return `${total.toLocaleString('ru-RU')} обращений, ${problems.toLocaleString('ru-RU')} проблемных`
  }
  return `${total.toLocaleString('ru-RU')} обращений`
}
