const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? body.message ?? JSON.stringify(body)
    } catch {
      try {
        detail = await res.text()
      } catch {
        /* ignore */
      }
    }
    const err = new Error(detail || `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return res.text()
}

export const api = {
  health() {
    return request('/api/v1/health')
  },

  uploadDataset(file, params = {}) {
    const fd = new FormData()
    fd.append('file', file)
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== '') qs.set(k, String(v))
    })
    const query = qs.toString()
    return request(`/api/v1/dataset/upload${query ? `?${query}` : ''}`, {
      method: 'POST',
      body: fd,
    })
  },

  getJob(taskId) {
    return request(`/api/v1/jobs/${taskId}`)
  },

  getDashboard(taskId) {
    return request(`/api/v1/dashboard?task_id=${encodeURIComponent(taskId)}`)
  },

  getDistrictReport(taskId, districtId) {
    return request(
      `/api/v1/districts/${districtId}/report?task_id=${encodeURIComponent(taskId)}`,
    )
  },

  generateDistrictReport(taskId, districtId) {
    return request(`/api/v1/reports/generate?task_id=${encodeURIComponent(taskId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ district_id: districtId }),
    })
  },

  getGenerateStatus(genTaskId) {
    return request(`/api/v1/reports/generate/${genTaskId}`)
  },

  excelUrl(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/excel`
  },
}
