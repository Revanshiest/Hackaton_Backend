/** Demo-режим: снимок реального отчёта пайплайна (см. scripts/build_demo_snapshot.py). */

import demoSnapshot from './data/demoSnapshot.json'
import { mergeDashboard } from './api/adapters'

export const demoMeta = demoSnapshot.meta
export const demoPipelineSteps = demoSnapshot.pipeline_steps

export function getDemoMergedDashboard() {
  return mergeDashboard(demoSnapshot.dashboard)
}

export function getDemoDistrictReport(districtId) {
  return demoSnapshot.district_reports[String(districtId)] ?? null
}

export function getAllDemoDistrictReports() {
  return Object.values(demoSnapshot.district_reports).map((row) => row.data)
}
