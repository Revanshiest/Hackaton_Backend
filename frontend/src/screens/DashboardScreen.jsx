import { useEffect, useState } from 'react'
import { Zap, TrendingUp, AlertTriangle, RotateCcw, Eye, EyeOff, Loader2, Download, FileType, CalendarRange } from 'lucide-react'
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
    <div className="flex flex-col overflow-hidden" style={{ height: '100vh', background: 'var(--bg)' }}>
      <header
        className="px-5 py-3.5 flex items-center justify-between sticky top-0 z-50 shadow-sm"
        style={{ background: 'var(--head-bg)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-3 min-w-0">
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
              <p className="text-xs mt-0.5 flex items-center gap-1 truncate sm:hidden" style={{ color: 'var(--text-2)' }}>
                <CalendarRange className="w-3 h-3 flex-shrink-0" />
                {periodLabel}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex flex-col items-end gap-0.5 text-xs" style={{ color: 'var(--muted)' }}>
            {periodLabel && (
              <div className="flex items-center gap-1.5" style={{ color: 'var(--text-2)' }}>
                <CalendarRange className="w-3.5 h-3.5 flex-shrink-0" />
                <span>Период: {periodLabel}</span>
              </div>
            )}
            <div className="flex items-center gap-2">
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

      <LiveDemoPanel enabled={liveDemoOn} feed={liveFeed} />

      <div className="flex flex-row gap-0 overflow-hidden" style={{ height: 'calc(100vh - 57px)' }}>
        <div className="w-1/2 flex flex-col flex-shrink-0 p-4" style={{ height: '100%', paddingTop: '21px' }}>
          <div className="rounded-2xl overflow-hidden flex flex-col shadow-sm" style={{ ...card, height: '100%' }}>
            <div
              className="px-4 py-3 flex items-center gap-2 flex-shrink-0"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <TrendingUp className="w-4 h-4" style={{ color: 'var(--muted)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Карта Омской области</span>
              <span className="text-xs" style={{ color: 'var(--muted)' }}>кликните на район</span>
              <button
                onClick={() => setShowTiles((t) => !t)}
                className="ml-auto p-1 rounded-md transition-colors"
                style={{ color: showTiles ? 'var(--muted)' : '#dc2626' }}
              >
                {showTiles ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
              </button>
            </div>
            <div
              className="px-4 py-2 flex items-center gap-3 flex-shrink-0"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              {[['#22c55e', '75+'], ['#84cc16', '60–74'], ['#f97316', '50–59'], ['#ef4444', '35–49'], ['#991b1b', '<35']].map(
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

        <div className="w-1/2 flex flex-col gap-4 p-4 overflow-hidden min-h-0">
          <div className="flex-shrink-0">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-red-500" />
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text-2)' }}>Критические районы</h2>
              <span className="text-xs" style={{ color: 'var(--muted)' }}>· требуют первоочередного внимания</span>
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              {critical.map((d, i) => (
                <DistrictCard key={d.id} district={d} rank={i + 1} onClick={() => onDistrictClick(d)} />
              ))}
            </div>
          </div>

          <div className="flex-1 rounded-2xl overflow-hidden flex flex-col shadow-sm min-h-0" style={{ ...card }}>
            <div
              className="px-4 py-3 flex items-center gap-2 flex-shrink-0"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <AlertTriangle className="w-4 h-4 text-orange-500" />
              <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
                Топ-10 проблемных районов
              </span>
              <span className="text-xs" style={{ color: 'var(--muted)' }}>выше индекс — больше проблем</span>
              {(taskId || (isDemo && demoMeta.source_job)) && (
                <button
                  type="button"
                  onClick={() => window.open(api.excelTop10Url(isDemo ? demoMeta.source_job : taskId), '_blank')}
                  className="ml-auto flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-lg transition-colors hover:opacity-90"
                  style={{ border: '1px solid var(--border)', color: 'var(--text-2)', background: 'var(--bg-card)' }}
                >
                  <Download className="w-3.5 h-3.5" />
                  Excel Top-10
                </button>
              )}
            </div>
            <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0">
              <Top10Table districts={top10} onDistrictClick={onDistrictClick} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
