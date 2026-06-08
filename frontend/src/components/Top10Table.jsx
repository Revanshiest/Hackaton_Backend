const scoreColor = (s) => s >= 75 ? '#22c55e' : s >= 60 ? '#84cc16' : s >= 50 ? '#f97316' : s >= 35 ? '#ef4444' : '#991b1b'

export default function Top10Table({ districts, onDistrictClick }) {
  return (
    <table className="w-full text-sm table-fixed">
      <thead className="sticky top-0 z-10" style={{ background: 'var(--bg-card)' }}>
        <tr style={{ borderBottom: '1px solid var(--border)' }}>
          <th className="text-left px-4 py-2.5 text-xs font-semibold w-8" style={{ color: 'var(--muted)' }}>#</th>
          <th className="text-left px-3 py-2.5 text-xs font-semibold" style={{ color: 'var(--muted)' }}>Район</th>
          <th className="text-right px-3 py-2.5 text-xs font-semibold w-14" style={{ color: 'var(--muted)' }}>Скор</th>
          <th className="text-left px-3 py-2.5 text-xs font-semibold w-24" style={{ color: 'var(--muted)' }}>Проблема</th>
        </tr>
      </thead>
      <tbody>
        {districts.map((d, i) => (
          <tr
            key={d.id}
            onClick={() => onDistrictClick(d)}
            className="cursor-pointer transition-colors"
            style={{ borderBottom: '1px solid var(--border)' }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-sub)'}
            onMouseLeave={e => e.currentTarget.style.background = ''}
          >
            <td className="px-4 py-3 text-xs font-medium" style={{ color: 'var(--muted)' }}>{i + 1}</td>
            <td className="px-3 py-3 font-medium truncate" style={{ color: 'var(--text)' }}>{d.name}</td>
            <td className="px-3 py-3 text-right">
              <span className="font-bold tabular-nums text-sm" style={{ color: scoreColor(d.score) }}>{d.score}</span>
            </td>
            <td className="px-3 py-3 text-xs truncate" style={{ color: 'var(--muted)' }}>{d.topProblem}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
