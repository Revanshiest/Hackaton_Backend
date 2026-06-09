import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, Clock, Loader2 } from 'lucide-react'
import { api } from '../api/client'
import { demoPipelineSteps } from '../demo'

function formatDuration(sec) {
  if (sec == null || Number.isNaN(sec)) return '—'
  const value = Number(sec)
  if (value < 60) return `${value} с`
  const minutes = Math.floor(value / 60)
  const seconds = Math.round(value % 60)
  return seconds ? `${minutes} м ${seconds} с` : `${minutes} м`
}

function mergePipelineSteps(apiSteps) {
  const byId = Object.fromEntries((apiSteps || []).map((step) => [step.id, step]))
  return demoPipelineSteps.map((def) => {
    const api = byId[def.id] || {}
    return {
      id: def.id,
      label: def.label,
      description: def.description,
      status: api.status || 'pending',
      detail: api.detail || '',
      duration_sec: api.duration_sec ?? null,
    }
  })
}

export default function TaskTimingPopover({ taskId, isDemo, sourceJob }) {
  const effectiveId = taskId || sourceJob
  const [open, setOpen] = useState(false)
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0 })
  const ref = useRef(null)

  useEffect(() => {
    if (!open || !effectiveId) return
    let cancelled = false
    setLoading(true)
    setError('')
    api
      .getJob(effectiveId)
      .then((data) => {
        if (!cancelled) setJob(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setJob(null)
          setError(err.message || 'Не удалось загрузить')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, effectiveId])

  useEffect(() => {
    const onDocClick = (event) => {
      if (ref.current && !ref.current.contains(event.target)) {
        const panel = document.getElementById('task-timing-panel')
        if (panel && panel.contains(event.target)) return
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  const openPanel = () => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect()
      setPanelPos({
        top: rect.bottom + 8,
        left: Math.min(rect.left, window.innerWidth - 360),
      })
    }
    setOpen(true)
  }

  if (!effectiveId) {
    return (
      <span className="text-sm" style={{ color: 'var(--muted)' }}>
        · Demo-снимок
      </span>
    )
  }

  const steps = mergePipelineSteps(job?.steps)
  const totalSec = job?.stats?.elapsed_sec

  const panel = open ? (
    <div
      id="task-timing-panel"
      className="rounded-xl shadow-xl p-4 anim-up"
      style={{
        position: 'fixed',
        top: panelPos.top,
        left: panelPos.left,
        zIndex: 9999,
        width: 'min(24rem, calc(100vw - 1.5rem))',
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        maxHeight: 'min(70vh, 28rem)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div className="flex items-center gap-2 mb-3 flex-shrink-0">
        <Clock className="w-4 h-4 text-red-600" />
        <p className="text-base font-semibold" style={{ color: 'var(--text)' }}>
          Время по этапам
        </p>
        {totalSec != null && (
          <span className="ml-auto text-sm font-medium" style={{ color: 'var(--muted)' }}>
            всего {formatDuration(totalSec)}
          </span>
        )}
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-4 text-sm" style={{ color: 'var(--muted)' }}>
          <Loader2 className="w-4 h-4 animate-spin" />
          Загрузка…
        </div>
      )}

      {!loading && error && <p className="text-sm text-red-600 py-2">{error}</p>}

      {!loading && !error && (
        <ul className="space-y-0 overflow-y-auto flex-1 pr-1">
          {steps.map((step) => (
            <li
              key={step.id}
              className="flex items-start justify-between gap-3 py-2.5 border-b last:border-0"
              style={{ borderColor: 'var(--border)' }}
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold leading-snug" style={{ color: 'var(--text)' }}>
                  {step.label}
                </p>
                {(step.detail || step.description) && (
                  <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--muted)' }}>
                    {step.detail || step.description}
                  </p>
                )}
              </div>
              <span
                className="font-mono text-sm font-bold flex-shrink-0 tabular-nums pt-0.5"
                style={{ color: step.duration_sec != null ? 'var(--text-2)' : 'var(--muted)' }}
              >
                {formatDuration(step.duration_sec)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {!loading && !error && isDemo && (
        <p className="text-xs mt-3 flex-shrink-0" style={{ color: 'var(--muted)' }}>
          Demo-снимок · исходная задача {effectiveId}
        </p>
      )}
    </div>
  ) : null

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => (open ? setOpen(false) : openPanel())}
        className="inline-flex items-center gap-1 text-sm font-medium transition-colors hover:opacity-80"
        style={{ color: 'var(--text-2)' }}
        aria-expanded={open}
      >
        <span style={{ color: 'var(--muted)' }}>·</span>
        <span>задача</span>
        <span className="font-mono underline decoration-dotted underline-offset-2">{effectiveId}</span>
        <ChevronDown
          className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`}
          style={{ color: 'var(--muted)' }}
        />
      </button>
      {panel && createPortal(panel, document.body)}
    </div>
  )
}
