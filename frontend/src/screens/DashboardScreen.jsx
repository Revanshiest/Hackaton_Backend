import { useEffect, useState } from 'react'
import { Zap, TrendingUp, AlertTriangle, RotateCcw, Eye, EyeOff, Loader2, Download, FileType, CalendarRange, Archive } from 'lucide-react'
import { getAllDemoDistrictReports, getDemoMergedDashboard, demoMeta } from '../demo'
import { api } from '../api/client'
import { mergeDashboard } from '../api/adapters'
import { formatPeriod, formatIncidentStats } from '../utils/formatPeriod'
import OmskMap from '../components/OmskMap'
import Top10Table from '../components/Top10Table'
import DistrictCard from '../components/DistrictCard'
import ThemeToggle from '../components/ThemeToggle'
import TaskTimingPopover from '../components/TaskTimingPopover'
import LiveDemoPanel, { LiveDemoToggle } from '../components/LiveDemoPanel'
import DepartmentReportsModal from '../components/DepartmentReportsModal'
import { useLiveDemoFeed } from '../hooks/useLiveDemoFeed'

const card = {
  background: 'var(--bg-card)',
  borderColor: 'var(--border)',
  borderWidth: 1,
  borderStyle: 'solid',
}

export default function DashboardScreen({
  taskId,
  isDemo,
  onDistrictClick,
  onReset,
  dark,
  onToggleTheme,
}) {
  const [districts, setDistricts] = useState([])
  const [top10, setTop10] = useState([])
  const [critical, setCritical] = useState([])
  const [periodLabel, setPeriodLabel] = useState(null)
  const [statsLabel, setStatsLabel] = useState(null)
  const [loading, setLoading] = useState(!isDemo)
  const [error, setError] = useState('')
  const [showTiles, setShowTiles] = useState(true)
  const [exportingRegionPdf, setExportingRegionPdf] = useState(false)
  const [deptModalOpen, setDeptModalOpen] = useState(false)
  const [liveDemoOn, setLiveDemoOn] = useState(false)
  const liveFeed = useLiveDemoFeed(liveDemoOn)

  const applyDashboardMeta = (merged, meta = null) => {
    const start = merged.startDate ?? meta?.start_date
    const end = merged.endDate ?? meta?.end_date
    setPeriodLabel(formatPeriod(start, end))
    setStatsLabel(
      formatIncidentStats({
        totalIncidents: merged.totalIncidents ?? meta?.rows_total,
        problemCount: merged.problemCount ?? meta?.problem_count,
      }),
    )
  }

  const handleRegionPdf = async () => {
    if (exportingRegionPdf) return
    setExportingRegionPdf(true)
    try {
      if (isDemo || !taskId) {
        await api.downloadRegionPdfFromData(getAllDemoDistrictReports())
      } else {
        await api.downloadRegionPdf(taskId)
      }
    } catch (err) {
      console.error(err)
      alert(err.message || 'Не удалось сформировать сводный PDF.')
    } finally {
      setExportingRegionPdf(false)
    }
  }

  const effectiveTaskId = isDemo ? demoMeta.source_job : taskId

  const handleDepartmentReports = () => {
    if (!effectiveTaskId) return
    setDeptModalOpen(true)
  }

  useEffect(() => {
    if (isDemo || !taskId) {
      const merged = getDemoMergedDashboard()
      setDistricts(merged.districts)
      setTop10(merged.top10)
      setCritical(merged.critical)
      applyDashboardMeta(merged, demoMeta)
      setLoading(false)
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const dashboard = await api.getDashboard(taskId)
        if (cancelled) return
        const merged = mergeDashboard(dashboard)
        setDistricts(merged.districts)
        setTop10(merged.top10)
        setCritical(merged.critical)
        applyDashboardMeta(merged)
      } catch (err) {
        if (cancelled) return
        const msg = err.message || ''
        if (err.status === 409 || msg.includes('не готова') || msg.includes('running')) {
          setError('Обработка ещё идёт. Подождите завершения на экране прогресса.')
          return
        }
        setError(msg || 'Не удалось загрузить дашборд')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => { cancelled = true }
  }, [taskId, isDemo])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center gap-3" style={{ background: 'var(--bg)' }}>
        <Loader2 className="w-6 h-6 animate-spin text-red-600" />
        <span style={{ color: 'var(--text-2)' }}>Загрузка дашборда…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-4" style={{ background: 'var(--bg)' }}>
        <p className="text-red-600 text-sm">{error}</p>
        <button onClick={onReset} className="text-sm underline" style={{ color: 'var(--muted)' }}>
          Загрузить другой файл
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen min-h-0 overflow-hidden" style={{ background: 'var(--bg)' }}>
      <header
        className="px-3 sm:px-5 py-3 sm:py-3.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 sticky top-0 z-50 shadow-sm"
        style={{ background: 'var(--head-bg)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
          <div className="w-7 h-7 rounded-lg bg-red-600 flex items-center justify-center flex-shrink-0">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold tracking-tight text-base" style={{ color: 'var(--text)' }}>ZeroProblems</span>
              <TaskTimingPopover taskId={taskId} isDemo={isDemo} sourceJob={isDemo ? demoMeta.source_job : null} />
              <LiveDemoToggle enabled={liveDemoOn} onToggle={() => setLiveDemoOn((v) => !v)} />
            </div>
            {periodLabel && (
              <p className="text-xs mt-0.5 flex items-center gap-1 truncate md:hidden" style={{ color: 'var(--text-2)' }}>
                <CalendarRange className="w-3 h-3 flex-shrink-0" />
                {periodLabel}
                {statsLabel && <span className="truncate"> · {statsLabel}</span>}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-3 flex-shrink-0 flex-wrap justify-end">
          <div className="hidden md:flex flex-col items-end gap-0.5 text-xs max-w-[min(100%,28rem)]" style={{ color: 'var(--muted)' }}>
            {periodLabel && (
              <div className="flex items-center gap-1.5" style={{ color: 'var(--text-2)' }}>
                <CalendarRange className="w-3.5 h-3.5 flex-shrink-0" />
                <span>Период: {periodLabel}</span>
              </div>
            )}
            <div className="flex items-center gap-2 flex-wrap justify-end">
              {isDemo ? (
                <>
                  <div className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  Снимок от {demoMeta.generated_at?.slice(0, 10) ?? '—'} · {demoMeta.municipalities} МО
                </>
              ) : (
                <>
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Данные актуальны
                </>
              )}
              {statsLabel && <span>· {statsLabel}</span>}
            </div>
          </div>
          {(taskId || (isDemo && demoMeta.source_job)) && (
            <button
              type="button"
              onClick={() => window.open(api.excelUrl(isDemo ? demoMeta.source_job : taskId), '_blank')}
              className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-lg transition-colors hover:opacity-90"
              style={{
                border: '1px solid var(--border)',
                color: 'var(--text-2)',
                background: 'var(--bg-card)',
              }}
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:block">Excel все МО</span>
            </button>
          )}
          <button
            type="button"
            onClick={handleRegionPdf}
            disabled={exportingRegionPdf}
            className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-lg transition-colors"
            style={{
              border: '1px solid #b91c1c',
              background: '#dc2626',
              color: '#fff',
              opacity: exportingRegionPdf ? 0.6 : 1,
            }}
          >
            <FileType className="w-3.5 h-3.5" />
            <span className="hidden sm:block">{exportingRegionPdf ? 'PDF…' : 'PDF все МО'}</span>
          </button>
          {effectiveTaskId && (
            <button
              type="button"
              onClick={handleDepartmentReports}
              className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-lg transition-colors hover:opacity-90"
              style={{
                border: '1px solid var(--border)',
                color: 'var(--text-2)',
                background: 'var(--bg-card)',
              }}
              title="ZIP с PDF и Excel для каждого ведомства по муниципалитетам"
            >
              <Archive className="w-3.5 h-3.5" />
              <span className="hidden lg:block">Отчёты в ведомства</span>
            </button>
          )}
          <button
            onClick={onReset}
            className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-md transition-colors"
            style={{ color: 'var(--muted)' }}
          >
            <RotateCcw className="w-3 h-3" />
            <span className="hidden sm:block">Новый файл</span>
          </button>
          <ThemeToggle dark={dark} onToggle={onToggleTheme} />
        </div>
      </header>

      <DepartmentReportsModal
        taskId={effectiveTaskId}
        open={deptModalOpen}
        onClose={() => setDeptModalOpen(false)}
      />

      <LiveDemoPanel enabled={liveDemoOn} feed={liveFeed} />

      <div className="flex-1 flex flex-col xl:flex-row min-h-0 overflow-y-auto xl:overflow-hidden">
        <div className="w-full xl:w-[46%] 2xl:w-[44%] flex flex-col flex-shrink-0 p-3 sm:p-4 xl:min-h-0 h-[min(48vh,440px)] xl:h-auto xl:max-h-full xl:flex-1">
          <div className="rounded-2xl overflow-hidden flex flex-col shadow-sm flex-1 min-h-[240px]" style={{ ...card }}>
            <div
              className="px-3 sm:px-4 py-2.5 sm:py-3 flex items-center gap-2 flex-shrink-0 flex-wrap"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <TrendingUp className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--muted)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Карта Омской области</span>
              <span className="text-xs hidden sm:inline" style={{ color: 'var(--muted)' }}>кликните на район</span>
              <button
                onClick={() => setShowTiles((t) => !t)}
                className="ml-auto p-1 rounded-md transition-colors"
                style={{ color: showTiles ? 'var(--muted)' : '#dc2626' }}
              >
                {showTiles ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
              </button>
            </div>
            <div
              className="px-3 sm:px-4 py-2 flex flex-wrap items-center gap-x-3 gap-y-1 flex-shrink-0"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              {[['#991b1b', '75+'], ['#ef4444', '60–74'], ['#f97316', '50–59'], ['#84cc16', '35–49'], ['#22c55e', '<35']].map(
                ([c, l]) => (
                  <div key={l} className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-sm" style={{ background: c }} />
                    <span className="text-xs" style={{ color: 'var(--muted)' }}>{l}</span>
                  </div>
                ),
              )}
            </div>
            <div className="flex-1 min-h-0">
              <OmskMap districts={districts} onDistrictClick={onDistrictClick} showTiles={showTiles} />
            </div>
          </div>
        </div>

        <div className="w-full xl:flex-1 xl:min-w-0 flex flex-col gap-3 sm:gap-4 p-3 sm:p-4 min-h-0 overflow-visible xl:overflow-y-auto xl:overscroll-contain pb-6 xl:pb-4">
          <div className="flex-shrink-0">
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text-2)' }}>Критические районы</h2>
              <span className="text-xs hidden sm:inline" style={{ color: 'var(--muted)' }}>· требуют первоочередного внимания</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-3 sm:gap-4">
              {critical.map((d, i) => (
                <DistrictCard key={d.id} district={d} rank={i + 1} onClick={() => onDistrictClick(d)} />
              ))}
            </div>
          </div>

          <div className="flex-shrink-0 rounded-2xl overflow-hidden flex flex-col shadow-sm" style={{ ...card }}>
            <div
              className="px-3 sm:px-4 py-2.5 sm:py-3 flex items-center gap-2 flex-shrink-0 flex-wrap"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <AlertTriangle className="w-4 h-4 text-orange-500 flex-shrink-0" />
              <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
                Топ-10 проблемных районов
              </span>
              <span className="text-xs hidden lg:inline" style={{ color: 'var(--muted)' }}>выше индекс — больше проблем</span>
              {(taskId || (isDemo && demoMeta.source_job)) && (
                <button
                  type="button"
                  onClick={() => window.open(api.excelTop10Url(isDemo ? demoMeta.source_job : taskId), '_blank')}
                  className="ml-auto flex items-center gap-1.5 text-xs font-medium px-2 sm:px-2.5 py-1 rounded-lg transition-colors hover:opacity-90"
                  style={{ border: '1px solid var(--border)', color: 'var(--text-2)', background: 'var(--bg-card)' }}
                >
                  <Download className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Excel Top-10</span>
                </button>
              )}
            </div>
            <div className="overflow-x-hidden">
              <Top10Table districts={top10} onDistrictClick={onDistrictClick} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
