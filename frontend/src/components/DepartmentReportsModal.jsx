import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  Archive,
  Building2,
  CheckCircle2,
  FileSpreadsheet,
  FileType,
  Loader2,
  MapPin,
  X,
} from 'lucide-react'
import { api } from '../api/client'

const PHASE_LABELS = {
  pdf: 'PDF',
  excel: 'Excel',
  archive: 'Архив',
  done: 'Готово',
  start: 'Старт',
}

function shortAgency(name) {
  if (!name) return ''
  const parts = name.split(' ')
  if (parts.length <= 4) return name
  return `${parts[0]} ${parts[1]}…`
}

function severityCount(agency, level) {
  const raw = agency?.counts?.[String(level)] ?? agency?.counts?.[level]
  const n = Number(raw)
  return Number.isFinite(n) ? n : 0
}

function sortAgenciesBySeverity(agencies) {
  return [...(agencies ?? [])].sort((a, b) => {
    const a4 = severityCount(a, 4)
    const b4 = severityCount(b, 4)
    if (b4 !== a4) return b4 - a4
    const a3 = severityCount(a, 3)
    const b3 = severityCount(b, 3)
    if (b3 !== a3) return b3 - a3
    return String(a.name).localeCompare(String(b.name), 'ru')
  })
}

export default function DepartmentReportsModal({ taskId, open, onClose }) {
  const [preview, setPreview] = useState(null)
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')
  const downloadedRef = useRef(false)
  const pollRef = useRef(null)
  const genTaskRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    document.body.classList.add('modal-open')
    return () => document.body.classList.remove('modal-open')
  }, [open])

  useEffect(() => {
    if (!open || !taskId) return undefined

    let cancelled = false
    setPreview(null)
    setStatus(null)
    setError('')
    downloadedRef.current = false
    genTaskRef.current = null

    const start = async () => {
      try {
        const [previewData, gen] = await Promise.all([
          api.getDepartmentReportsPreview(taskId),
          api.startDepartmentReportsGenerate(taskId),
        ])
        if (cancelled) return
        setPreview(previewData)
        setStatus(gen)
        genTaskRef.current = gen.task_id
        pollRef.current = setInterval(async () => {
          try {
            const next = await api.getDepartmentReportsStatus(gen.task_id)
            if (cancelled) return
            setStatus(next)
            if (next.status === 'completed') {
              clearInterval(pollRef.current)
              pollRef.current = null
              if (!downloadedRef.current) {
                downloadedRef.current = true
                await api.downloadDepartmentReportsByGenId(gen.task_id)
              }
            }
            if (next.status === 'failed') {
              clearInterval(pollRef.current)
              pollRef.current = null
              setError(next.message || 'Не удалось сформировать архив')
            }
          } catch (err) {
            if (!cancelled) {
              clearInterval(pollRef.current)
              pollRef.current = null
              setError(err.message || 'Ошибка при генерации')
            }
          }
        }, 600)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Не удалось запустить генерацию')
      }
    }

    start()
    return () => {
      cancelled = true
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [open, taskId])

  if (!open) return null

  const progress = Math.min(100, Math.round(status?.progress ?? 0))
  const isDone = status?.status === 'completed'
  const isRunning = status?.status === 'processing'
  const municipalities = preview?.municipalities ?? status?.preview?.municipalities ?? []
  const activeMuni = status?.current_municipality
  const activeAgency = status?.current_agency

  return createPortal(
    <div
      className="fixed inset-0 z-[10000] flex items-center justify-center p-3 sm:p-6"
      style={{ background: 'rgba(15, 23, 42, 0.55)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-2xl shadow-2xl flex flex-col"
        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="px-4 sm:px-5 py-4 flex items-start gap-3 flex-shrink-0"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: '#fff1f2', color: '#dc2626' }}
          >
            <Archive className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold" style={{ color: 'var(--text)' }}>
              Отчёты в ведомства
            </h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
              PDF и Excel по каждому муниципалитету и ведомству
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--muted)' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-4 sm:px-5 py-4 overflow-y-auto flex-1 space-y-4">
          {error ? (
            <div
              className="rounded-xl px-4 py-3 text-sm"
              style={{ background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}
            >
              {error}
              <p className="text-xs mt-2 opacity-80">
                Убедитесь, что API перезапущен после обновления. Для demo загрузите свой Excel-файл.
              </p>
            </div>
          ) : null}

          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            {[
              { label: 'Муниципалитетов', value: preview?.municipalities_count ?? '—', icon: MapPin },
              { label: 'Ведомств', value: preview?.agencies_count ?? '—', icon: Building2 },
              { label: 'Отчётов', value: preview?.reports_count ?? '—', icon: FileType },
            ].map(({ label, value, icon: Icon }) => (
              <div
                key={label}
                className="rounded-xl px-3 py-3 text-center"
                style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}
              >
                <Icon className="w-4 h-4 mx-auto mb-1.5" style={{ color: '#dc2626' }} />
                <div className="text-lg font-bold" style={{ color: 'var(--text)' }}>{value}</div>
                <div className="text-[10px] sm:text-xs" style={{ color: 'var(--muted)' }}>{label}</div>
              </div>
            ))}
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium" style={{ color: 'var(--text-2)' }}>
                {isDone ? 'Архив сформирован' : isRunning ? 'Генерация…' : 'Подготовка…'}
              </span>
              <span className="text-xs font-semibold" style={{ color: '#dc2626' }}>{progress}%</span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg)' }}>
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${progress}%`,
                  background: isDone
                    ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                    : 'linear-gradient(90deg, #dc2626, #ea580c)',
                }}
              />
            </div>
            {status?.message ? (
              <p className="text-xs mt-2 flex items-center gap-1.5" style={{ color: 'var(--muted)' }}>
                {isRunning ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                {isDone ? <CheckCircle2 className="w-3 h-3 text-emerald-500" /> : null}
                {status.message}
              </p>
            ) : null}
            {status?.phase && isRunning ? (
              <div className="flex gap-2 mt-2 flex-wrap">
                {['pdf', 'excel', 'archive'].map((phase) => (
                  <span
                    key={phase}
                    className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                    style={{
                      background: status.phase === phase ? '#fff1f2' : 'var(--bg)',
                      color: status.phase === phase ? '#dc2626' : 'var(--muted)',
                      border: `1px solid ${status.phase === phase ? '#fecaca' : 'var(--border)'}`,
                    }}
                  >
                    {PHASE_LABELS[phase]}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>
              Структура архива
            </h3>
            <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
              {municipalities.length === 0 ? (
                <div className="text-xs py-6 text-center" style={{ color: 'var(--muted)' }}>
                  <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-red-500" />
                  Загрузка структуры…
                </div>
              ) : (
                municipalities.map((muni) => {
                  const muniActive = activeMuni === muni.name
                  return (
                    <div
                      key={muni.name}
                      className="rounded-xl overflow-hidden"
                      style={{
                        border: `1px solid ${muniActive ? '#fecaca' : 'var(--border)'}`,
                        background: muniActive ? '#fffafb' : 'var(--bg)',
                      }}
                    >
                      <div
                        className="px-3 py-2 flex items-center gap-2 text-xs font-semibold"
                        style={{ color: 'var(--text)' }}
                      >
                        <MapPin className="w-3.5 h-3.5 flex-shrink-0" style={{ color: '#dc2626' }} />
                        <span className="truncate">{muni.name}</span>
                        <span className="ml-auto text-[10px] font-normal" style={{ color: 'var(--muted)' }}>
                          {muni.agencies?.length ?? 0} вед.
                        </span>
                      </div>
                      <div className="px-2 pb-2 space-y-1">
                        {sortAgenciesBySeverity(muni.agencies).map((agency) => {
                          const active = muniActive && activeAgency === agency.name
                          const sev4 = severityCount(agency, 4)
                          const sev3 = severityCount(agency, 3)
                          return (
                            <div
                              key={`${muni.name}-${agency.name}`}
                              className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-[11px]"
                              style={{
                                background: active ? '#fff1f2' : 'var(--bg-card)',
                                border: `1px solid ${active ? '#fecaca' : 'transparent'}`,
                              }}
                            >
                              {active && isRunning ? (
                                <Loader2 className="w-3 h-3 animate-spin flex-shrink-0 text-red-500" />
                              ) : (
                                <Building2 className="w-3 h-3 flex-shrink-0" style={{ color: 'var(--muted)' }} />
                              )}
                              <span className="flex-1 truncate" style={{ color: 'var(--text-2)' }} title={agency.name}>
                                {shortAgency(agency.name)}
                              </span>
                              <div className="flex items-center gap-1 flex-shrink-0">
                                {sev4 > 0 ? (
                                  <span
                                    className="px-1.5 py-0.5 rounded font-semibold whitespace-nowrap"
                                    style={{ background: '#fef2f2', color: '#dc2626' }}
                                  >
                                    {sev4} крит.
                                  </span>
                                ) : null}
                                {sev3 > 0 ? (
                                  <span
                                    className="px-1.5 py-0.5 rounded font-semibold whitespace-nowrap"
                                    style={{ background: '#fff7ed', color: '#ea580c' }}
                                  >
                                    {sev3} тяж.
                                  </span>
                                ) : null}
                              </div>
                              <span className="flex items-center gap-0.5" style={{ color: 'var(--muted)' }}>
                                <FileType className="w-3 h-3" />
                                <FileSpreadsheet className="w-3 h-3" />
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>

        <div
          className="px-4 sm:px-5 py-3 flex items-center justify-end gap-2 flex-shrink-0"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          {isDone && genTaskRef.current ? (
            <button
              type="button"
              onClick={() => api.downloadDepartmentReportsByGenId(genTaskRef.current)}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg"
              style={{ background: '#dc2626', color: '#fff' }}
            >
              Скачать снова
            </button>
          ) : null}
          <button
            type="button"
            onClick={onClose}
            className="text-xs font-medium px-3 py-1.5 rounded-lg"
            style={{ border: '1px solid var(--border)', color: 'var(--text-2)' }}
          >
            {isDone ? 'Закрыть' : 'Свернуть'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
