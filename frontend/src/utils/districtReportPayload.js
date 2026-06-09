/** UI district → тело DistrictReport для API (PDF и др.). */

export function districtToReportPayload(district) {
  const total =
    district.totalIncidents
    ?? district.problems?.reduce((s, p) => s + p.count, 0)
    ?? 0

  return {
    district_id: district.id,
    district_name: district.name,
    score: district.score,
    analytical_summary: district.summary || '',
    total_incidents: total,
    top_category: district.topProblem || '—',
    categories_count: district.problems?.length ?? 0,
    themes_stat: (district.problems || []).map((p) => ({
      group_name: p.category,
      count: p.count,
      percentage: total ? Math.round((p.count / total) * 1000) / 10 : 0,
    })),
    severity_stat: (district.severityStat || []).map((s) => ({
      severity: s.severity,
      label: s.label,
      count: s.count,
      percentage: s.percentage,
    })),
    incident_examples: (district.examples || [])
      .map((e) => (typeof e === 'string'
        ? { text: e, severity: 1, label: 'Низкая' }
        : { text: e.text, severity: e.severity, label: e.label }))
      .filter((e) => e.severity > 0),
  }
}
