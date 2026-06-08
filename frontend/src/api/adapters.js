/** API → формат UI-компонентов */

export function districtFromShort(info) {
  return {
    id: info.district_id,
    name: info.district_name,
    score: info.score,
    topProblem: info.main_problem || '—',
    coords: info.center_coordinates ?? null,
    problems: [],
    examples: [],
    summary: '',
  }
}

export function districtFromCritical(card) {
  const problems = (card.top_themes || []).map((t) => ({
    category: t.theme,
    count: t.count,
  }))
  return {
    id: card.district_id,
    name: card.district_name,
    score: card.score,
    topProblem: problems[0]?.category || '—',
    coords: null,
    problems,
    examples: card.sample_incident_text ? [card.sample_incident_text] : [],
    summary: card.sample_incident_text || '',
    criticalityStatus: card.criticality_status,
    totalIncidents: card.total_incidents,
  }
}

export function districtFromReport(data) {
  return {
    id: data.district_id,
    name: data.district_name,
    score: data.score,
    topProblem: data.top_category || '—',
    summary: data.analytical_summary || '',
    problems: (data.themes_stat || []).map((t) => ({
      category: t.group_name,
      count: t.count,
    })),
    examples: data.incident_examples || [],
    totalIncidents: data.total_incidents,
  }
}

export function mergeDashboard(dashboard) {
  const byId = new Map()

  ;(dashboard.map_data || []).forEach((row) => {
    byId.set(row.district_id, districtFromShort(row))
  })

  ;(dashboard.top_districts || []).forEach((row) => {
    const prev = byId.get(row.district_id) || {}
    byId.set(row.district_id, { ...prev, ...districtFromShort(row) })
  })

  ;(dashboard.critical_districts || []).forEach((row) => {
    const prev = byId.get(row.district_id) || {}
    byId.set(row.district_id, { ...prev, ...districtFromCritical(row) })
  })

  const districts = Array.from(byId.values())
  const top10 = (dashboard.top_districts || []).map((row) => byId.get(row.district_id)).filter(Boolean)
  const critical = (dashboard.critical_districts || []).map((row) => byId.get(row.district_id)).filter(Boolean)

  return { districts, top10, critical }
}
