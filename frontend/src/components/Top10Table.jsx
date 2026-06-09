import { ChevronRight } from 'lucide-react'
import { scoreColor } from '../utils/scoreColor'

const RANK_BADGE = {
  bg: 'var(--bg-sub)',
  color: 'var(--text-2)',
  border: 'var(--border)',
}

export default function Top10Table({ districts, onDistrictClick }) {
  if (!districts.length) {
    return (
      <p className="px-4 py-8 text-center text-sm" style={{ color: 'var(--muted)' }}>
        Нет данных для рейтинга
      </p>
    )
  }

  return (
    <div>
      {districts.map((d, i) => {
        const color = scoreColor(d.score)
        return (
          <button
            key={d.id}
            type="button"
            onClick={() => onDistrictClick(d)}
            className="group w-full text-left px-4 py-3.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500/30"
            style={{ borderBottom: '1px solid var(--border)' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg-sub)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = ''
            }}
          >
            <div className="flex items-start gap-3">
              <span
                className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold mt-0.5"
                style={{
                  background: RANK_BADGE.bg,
                  color: RANK_BADGE.color,
                  border: `1px solid ${RANK_BADGE.border}`,
                }}
              >
                {i + 1}
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3 mb-1.5">
                  <div className="min-w-0">
                    <p className="font-semibold text-sm leading-snug" style={{ color: 'var(--text)' }}>
                      {d.name}
                    </p>
                    {d.topProblem && d.topProblem !== '—' && (
                      <p
                        className="mt-1 text-xs leading-snug line-clamp-2"
                        style={{ color: 'var(--text-2)' }}
                        title={d.topProblem}
                      >
                        {d.topProblem}
                      </p>
                    )}
                  </div>
                  <span
                    className="flex-shrink-0 inline-flex items-center justify-center min-w-[2.25rem] px-2 py-1 rounded-lg font-bold tabular-nums text-sm"
                    style={{ background: `${color}18`, color }}
                  >
                    {d.score}
                  </span>
                </div>
                {d.summary && (
                  <p
                    className="text-xs leading-relaxed line-clamp-3"
                    style={{ color: 'var(--muted)' }}
                    title={d.summary}
                  >
                    {d.summary}
                  </p>
                )}
              </div>

              <ChevronRight
                className="w-4 h-4 flex-shrink-0 mt-1 opacity-0 group-hover:opacity-60 transition-opacity"
                style={{ color: 'var(--muted)' }}
              />
            </div>
          </button>
        )
      })}
    </div>
  )
}
