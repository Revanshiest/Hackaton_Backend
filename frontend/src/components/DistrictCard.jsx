import { ArrowRight } from 'lucide-react'

import { scoreColor } from '../utils/scoreColor'
const rankLabel  = ['Критичный', 'Очень высокий', 'Высокий']

export default function DistrictCard({ district, rank, onClick }) {
  const color = scoreColor(district.score)
  const total = district.totalIncidents ?? district.problems.reduce((s, p) => s + p.count, 0)
  const label = district.criticalityStatus || rankLabel[rank - 1]

  return (
    <div
      onClick={onClick}
      className="rounded-2xl p-4 sm:p-5 cursor-pointer transition-all duration-200 shadow-sm h-full flex flex-col"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = color; e.currentTarget.style.boxShadow = `0 4px 20px ${color}22` }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = '' }}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <span className="inline-block text-xs font-bold uppercase tracking-wider mb-1.5 px-2 py-0.5 rounded-full"
            style={{ color, background: `${color}18` }}>
            {label}
          </span>
          <h3 className="font-bold text-sm sm:text-base leading-tight break-words" style={{ color: 'var(--text)' }}>{district.name}</h3>
        </div>
        <div className="text-2xl sm:text-3xl font-black tabular-nums flex-shrink-0 ml-2" style={{ color }}>{district.score}</div>
      </div>

      <div className="h-1.5 rounded-full overflow-hidden mb-4" style={{ background: 'var(--bg-sub)' }}>
        <div className="h-full rounded-full" style={{ width: `${district.score}%`, background: color }} />
      </div>

      <div className="space-y-2 mb-4">
        {(district.problems || []).slice(0, 3).map((p, i) => (
          <div key={p.category} className="flex justify-between items-start gap-2 text-xs">
            <span className="font-medium min-w-0 break-words" style={{ color: i === 0 ? 'var(--text)' : 'var(--muted)' }} title={p.category}>{p.category}</span>
            <span className="flex-shrink-0 tabular-nums" style={{ color: 'var(--muted)' }}>{p.count}</span>
          </div>
        ))}
      </div>

      {district.summary ? (
        <div className="pt-3 mb-3" style={{ borderTop: '1px solid var(--border)' }}>
          <p className="text-xs leading-relaxed line-clamp-4" style={{ color: 'var(--text-2)' }}>
            {district.summary}
          </p>
        </div>
      ) : (
        <div className="pt-3 mb-3" style={{ borderTop: '1px solid var(--border)' }}>
          <p className="text-xs leading-relaxed line-clamp-2 italic" style={{ color: 'var(--text-2)' }}>
            «{(district.examples || [])[0] || '—'}»
          </p>
        </div>
      )}

      <div className="flex items-center justify-between text-xs mt-auto pt-1" style={{ color: 'var(--muted)' }}>
        <span>{total} обращений</span>
        <div className="flex items-center gap-1">Подробнее <ArrowRight className="w-3 h-3" /></div>
      </div>
    </div>
  )
}
