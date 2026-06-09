import { useEffect } from 'react'
import { Activity, Radio, X } from 'lucide-react'
import { severityMeta } from '../utils/severityStyle'

function LiveToast({ event, onDismiss }) {
  const meta = severityMeta(event.severity)

  useEffect(() => {
    const t = setTimeout(() => onDismiss(event.uid), 9000)
    return () => clearTimeout(t)
  }, [event.uid, onDismiss])

  return (
    <div
      className="rounded-xl shadow-lg border p-3 animate-[slideIn_0.35s_ease-out] max-w-sm w-full"
      style={{
        background: 'var(--bg-card)',
        borderColor: meta.border,
        borderLeftWidth: 4,
        borderLeftColor: meta.accent,
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded"
              style={{ background: meta.bg, color: meta.accent }}
            >
              {event.label || meta.label}
            </span>
            <span className="text-[10px] truncate" style={{ color: 'var(--muted)' }}>
              {event.municipality || '—'}
            </span>
          </div>
          {event.topic && (
            <p className="text-xs mt-1 font-medium truncate" style={{ color: 'var(--text-2)' }}>
              {event.topic}
            </p>
          )}
          <p className="text-xs mt-1 line-clamp-3 leading-relaxed" style={{ color: 'var(--text)' }}>
            {event.text}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onDismiss(event.uid)}
          className="p-1 rounded-md flex-shrink-0"
          style={{ color: 'var(--muted)' }}
          aria-label="Закрыть"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

export function LiveDemoToggle({ enabled, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="inline-flex items-center gap-1 text-sm font-medium transition-colors hover:opacity-80"
      style={{ color: enabled ? '#16a34a' : 'var(--text-2)' }}
      title={enabled ? 'Выключить live demo' : 'Включить live demo'}
    >
      <span style={{ color: 'var(--muted)' }}>·</span>
      <Radio className={`w-3.5 h-3.5 ${enabled ? 'animate-pulse' : ''}`} />
      <span className="lowercase">live</span>
    </button>
  )
}

export default function LiveDemoPanel({ enabled, feed }) {
  const { events, received, total, dismiss } = feed

  return (
    <>
      {enabled && (
        <div
          className="fixed bottom-4 right-4 z-[200] flex flex-col gap-2 pointer-events-none"
          style={{ maxWidth: 'min(24rem, calc(100vw - 2rem))' }}
        >
          <div
            className="pointer-events-auto rounded-lg px-3 py-2 text-xs flex items-center gap-2 shadow-md border"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-2)' }}
          >
            <Activity className="w-3.5 h-3.5 text-emerald-500 animate-pulse" />
            <span>
              Поступило: <strong style={{ color: 'var(--text)' }}>{received}</strong>
              {total ? ` · пул ${total}` : ''}
            </span>
          </div>
          {events.map((event) => (
            <div key={event.uid} className="pointer-events-auto">
              <LiveToast event={event} onDismiss={dismiss} />
            </div>
          ))}
        </div>
      )}
    </>
  )
}
