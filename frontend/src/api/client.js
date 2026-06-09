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

  excelTop10Url(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/excel/top10`
  },

  districtPdfUrl(taskId, districtId) {
    return `${BASE}/api/v1/districts/${districtId}/report.pdf?task_id=${encodeURIComponent(taskId)}`
  },

  parseContentDisposition(header) {
    if (!header) return 'zeroproblems_report.pdf'
    const utf8 = header.match(/filename\*=UTF-8''([^;]+)/i)
    if (utf8?.[1]) {
      try {
        return decodeURIComponent(utf8[1])
      } catch {
        /* fall through */
      }
    }
    const ascii = header.match(/filename="([^"]+)"/i)
    return ascii?.[1] || 'zeroproblems_report.pdf'
  },

  async savePdfResponse(res) {
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new Error(detail || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const filename = api.parseContentDisposition(res.headers.get('content-disposition'))
    const url = URL.createObjectURL(blob)
    Object.assign(document.createElement('a'), { href: url, download: filename }).click()
    URL.revokeObjectURL(url)
  },

  async downloadDistrictPdf(taskId, districtId) {
    const res = await fetch(api.districtPdfUrl(taskId, districtId))
    return api.savePdfResponse(res)
  },

  async downloadDistrictPdfFromData(reportData) {
    const res = await fetch(`${BASE}/api/v1/reports/district/pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(reportData),
    })
    return api.savePdfResponse(res)
  },

  regionPdfUrl(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/report.pdf`
  },

  async downloadRegionPdf(taskId) {
    const res = await fetch(api.regionPdfUrl(taskId))
    return api.savePdfResponse(res)
  },

  async downloadRegionPdfFromData(districts, executiveSummary = '') {
    const res = await fetch(`${BASE}/api/v1/reports/region/pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ districts, executive_summary: executiveSummary }),
    })
    return api.savePdfResponse(res)
  },

  departmentReportsZipUrl(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments.zip`
  },

  departmentReportsDownloadUrl(taskId) {
    return `${BASE}/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments`
  },

  getDepartmentReportsPreview(taskId) {
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments/preview`)
  },

  startDepartmentReportsGenerate(taskId) {
    return request(`/api/v1/jobs/${encodeURIComponent(taskId)}/reports/departments/generate`, {
      method: 'POST',
    })
  },

  getDepartmentReportsStatus(genTaskId) {
    return request(`/api/v1/reports/departments/${encodeURIComponent(genTaskId)}`)
  },

  departmentReportsByGenUrl(genTaskId) {
    return `${BASE}/api/v1/reports/departments/${encodeURIComponent(genTaskId)}/download`
  },

  async saveZipResponse(res) {
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        detail = body.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new Error(detail || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const filename = api.parseContentDisposition(res.headers.get('content-disposition')) || 'zeroproblems_vedomstva.zip'
    const url = URL.createObjectURL(blob)
    Object.assign(document.createElement('a'), { href: url, download: filename }).click()
    URL.revokeObjectURL(url)
  },

  async downloadDepartmentReportsZip(taskId) {
    let res = await fetch(api.departmentReportsZipUrl(taskId))
    if (res.status === 404) {
      res = await fetch(api.departmentReportsDownloadUrl(taskId))
    }
    return api.saveZipResponse(res)
  },

  async downloadDepartmentReportsByGenId(genTaskId) {
    const res = await fetch(api.departmentReportsByGenUrl(genTaskId))
    return api.saveZipResponse(res)
  },
}
