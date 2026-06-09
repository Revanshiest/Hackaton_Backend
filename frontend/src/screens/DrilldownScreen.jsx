import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Download,
  Home,
  Route,
  Leaf,
  Bus,
  Lightbulb,
  TreeDeciduous,
  BotMessageSquare,
  FileSearch,
  Loader2,
} from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import ThemeToggle from '../components/ThemeToggle'
import { api } from '../api/client'
import { districtFromReport } from '../api/adapters'
import { getDemoDistrictReport } from '../demo'

const CATEGORY_ICONS = {
  ЖКХ: Home,
  Дороги: Route,
  Экология: Leaf,
  Транспорт: Bus,
  Освещение: Lightbulb,
  Благоустройство: TreeDeciduous,
}
const scoreColor = (s) => (s >= 75 ? '#22c55e' : s >= 60 ? '#84cc16' : s >= 50 ? '#f97316' : s >= 35 ? '#ef4444' : '#991b1b')

const SEVERITY_COLORS = {
  0: '#94a3b8',
  1: '#84cc16',
  2: '#eab308',
  3: '#f97316',
  4: '#dc2626',
}

const formatAppealText = (text) =>
  String(text)
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/^['"«»]+/, '')
    .replace(/\s+/g, ' ')
    .trim()

const SeverityTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div
      className="rounded-lg px-3 py-2 shadow-lg text-sm"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text)' }}
    >
      {row.label}: <strong>{row.count}</strong> ({row.percentage}%)
    </div>
  )
}

function splitCategoryLabel(text, maxChars = 34) {
  const value = String(text || '').trim()
  if (value.length <= maxChars) return [value]
  const words = value.split(/\s+/)
  const lines = []
  let line = ''
  for (const word of words) {
    const next = line ? `${line} ${word}` : word
    if (next.length > maxChars && line) {
      lines.push(line)
      line = word
    } else {
      line = next
    }
  }
  if (line) lines.push(line)
  if (lines.length > 2) {
    const merged = `${lines[0]} ${lines[1]}`
    return merged.length > maxChars + 6
      ? [`${merged.slice(0, maxChars - 1)}…`]
      : [lines[0], `${lines[1].slice(0, maxChars - 1)}…`]
  }
  return lines
}

function CategoryYAxisTick({ x, y, payload }) {
  const lines = splitCategoryLabel(payload?.value)
  return (
    <g transform={`translate(${x},${y})`}>
      {lines.map((line, i) => (
        <text
          key={i}
          x={0}
          y={0}
          dy={i * 11 + (lines.length === 1 ? 4 : -2)}
          textAnchor="end"
          fill="var(--text-2)"
          fontSize={10}
        >
          {line}
        </text>
      ))}
    </g>
  )
}

const chartBarHeight = (count) => Math.max(220, count * 46 + 32)

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-lg px-3 py-2 shadow-lg text-sm"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text)' }}
    >
      {payload[0].payload.category}: <strong>{payload[0].value}</strong>
    </div>
  )
}

export default function DrilldownScreen({ district: initialDistrict, taskId, isDemo, onBack, dark, onToggleTheme }) {
  const [district, setDistrict] = useState(initialDistrict)
  const [loading, setLoading] = useState(!!taskId)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    setDistrict(initialDistrict)
  }, [initialDistrict])

  useEffect(() => {
    if (isDemo || !taskId) {
      const snap = getDemoDistrictReport(initialDistrict.id)
      if (snap?.data) {
        setDistrict((prev) => ({ ...prev, ...districtFromReport(snap.data) }))
      }
      setLoading(false)
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const res = await api.getDistrictReport(taskId, initialDistrict.id)
        if (cancelled) return
        setDistrict((prev) => ({ ...prev, ...districtFromReport(res.data) }))
      } catch {
        /* keep preview from dashboard */
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => { cancelled = true }
  }, [taskId, isDemo, initialDistrict.id])

  const total =
    district.totalIncidents
    ?? district.problems.reduce((s, p) => s + p.count, 0)
  const color = scoreColor(district.score)
  const max = district.problems[0]?.count || 1

  const handleDownload = () => {
    if (taskId) {
      window.open(api.excelTop10Url(taskId), '_blank')
      return
    }
    const lines = [
      `Отчёт: ${district.name}`,
      `Скор: ${district.score}`,
      `Топ-проблема: ${district.topProblem}`,
      `Обращений: ${total}`,
      '',
      'Проблемы:',
      ...district.problems.map((p) => `  ${p.category}: ${p.count}`),
      '',
      'Сводка:',
      district.summary,
      '',
      'Примеры:',
      ...district.examples.map((e, i) => `  ${i + 1}. [${e.label || e.severity}] ${e.text}`),
    ]
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }))
    Object.assign(document.createElement('a'), {
      href: url,
      download: `zeroproblems-${district.id}.txt`,
    }).click()
    URL.revokeObjectURL(url)
  }

  const handleFullReport = async () => {
    if (!taskId) return
    setGenerating(true)
    try {
      const gen = await api.generateDistrictReport(taskId, district.id)
      const wait = async () => {
        const st = await api.getGenerateStatus(gen.task_id)
        if (st.status === 'completed') {
          const res = await api.getDistrictReport(taskId, district.id)
          setDistrict((prev) => ({ ...prev, ...districtFromReport(res.data) }))
          setGenerating(false)
          return
        }
        if (st.status === 'failed') {
          setGenerating(false)
          return
        }
        setTimeout(wait, 2000)
      }
      await wait()
    } catch {
      setGenerating(false)
    }
  }

  const card = { background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 16 }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center gap-3" style={{ background: 'var(--bg)' }}>
        <Loader2 className="w-6 h-6 animate-spin text-red-600" />
        <span style={{ color: 'var(--text-2)' }}>Загрузка отчёта…</span>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg)' }}>
      <header
        className="px-5 py-3.5 flex items-center gap-3 sticky top-0 z-50 shadow-sm"
        style={{ background: 'var(--head-bg)', borderBottom: '1px solid var(--border)' }}
      >
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm font-medium transition-colors"
          style={{ color: 'var(--text-2)' }}
        >
          <ArrowLeft className="w-4 h-4" /> Назад
        </button>
        <div className="w-px h-5" style={{ background: 'var(--border)' }} />
        <h1 className="font-bold" style={{ color: 'var(--text)' }}>{district.name}</h1>
        <span
          className="text-xs font-bold px-2 py-0.5 rounded-full"
          style={{ color, background: `${color}18` }}
        >
          Скор {district.score}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {taskId && (
            <button
              onClick={handleFullReport}
              disabled={generating}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
              style={{ background: '#dc2626', color: '#fff', border: '1px solid #b91c1c', opacity: generating ? 0.6 : 0.9 }}
            >
              <FileSearch className="w-3.5 h-3.5" />
              {generating ? 'Генерация…' : 'Полный отчёт'}
            </button>
          )}
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text-2)' }}
          >
            <Download className="w-3.5 h-3.5" /> {taskId && !isDemo ? 'Excel Top-10' : 'Скачать TXT'}
          </button>
          <ThemeToggle dark={dark} onToggle={onToggleTheme} />
        </div>
      </header>

      <div className="flex-1 p-4 lg:p-5 grid grid-cols-1 lg:grid-cols-2 gap-4 anim-up">
        <div className="space-y-4">
          <div className="p-5 shadow-sm" style={card}>
            <h2 className="text-sm font-semibold mb-5" style={{ color: 'var(--text)' }}>Обращения по категориям</h2>
            {district.problems.length ? (
              <ResponsiveContainer width="100%" height={chartBarHeight(district.problems.length)}>
                <BarChart
                  data={district.problems}
                  layout="vertical"
                  barSize={14}
                  margin={{ top: 4, right: 12, left: 4, bottom: 4 }}
                >
                  <XAxis type="number" tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis
                    dataKey="category"
                    type="category"
                    width={210}
                    tick={<CategoryYAxisTick />}
                    interval={0}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: `${color}08` }} />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                    {district.problems.map((_, i) => (
                      <Cell key={i} fill={i === 0 ? '#dc2626' : i === 1 ? '#ea580c' : '#94a3b8'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>Нет данных по категориям</p>
            )}
          </div>

          {district.problems.length > 0 && (
            <div className="p-5 shadow-sm" style={card}>
              <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text)' }}>Доли категорий</h2>
              <div className="space-y-3.5">
                {district.problems.map((p, i) => {
                  const Icon = CATEGORY_ICONS[p.category] || Home
                  return (
                    <div key={p.category} className="flex items-center gap-3">
                      <Icon className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--muted)' }} />
                      <div className="flex-1">
                        <div className="flex justify-between text-xs mb-1.5 gap-2">
                          <span className="font-medium leading-snug" style={{ color: 'var(--text-2)' }}>{p.category}</span>
                          <span style={{ color: 'var(--muted)' }}>
                            {p.count} · {Math.round((p.count / total) * 100)}%
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-sub)' }}>
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{
                              width: `${(p.count / max) * 100}%`,
                              background: i === 0 ? '#dc2626' : i === 1 ? '#ea580c' : '#94a3b8',
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="p-5 shadow-sm" style={card}>
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text)' }}>Примеры обращений</h2>
            <div className="space-y-3">
              {(district.examples.length ? district.examples : [{ text: 'Нет примеров', severity: 0, label: '' }]).map((item, i) => {
                const text = formatAppealText(typeof item === 'string' ? item : item.text)
                const severity = typeof item === 'string' ? 1 : item.severity
                const label = typeof item === 'string' ? '' : item.label
                const badgeColor = SEVERITY_COLORS[severity] ?? '#94a3b8'
                return (
                  <div
                    key={i}
                    className="flex gap-3 p-3.5 rounded-xl"
                    style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}
                  >
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
                      style={{ background: 'var(--border)', color: 'var(--text-2)' }}
                    >
                      {i + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      {severity > 0 && label && (
                        <span
                          className="inline-block text-xs font-semibold px-2 py-0.5 rounded-full mb-1.5"
                          style={{ background: `${badgeColor}22`, color: badgeColor }}
                        >
                          {label} · {severity}
                        </span>
                      )}
                      <p className="text-sm leading-relaxed" style={{ color: 'var(--text-2)' }}>{text}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Всего обращений', value: total, sub: 'за период' },
              { label: 'Индекс', value: district.score, sub: 'из 100', color },
              { label: 'Топ-категория', value: district.topProblem, sub: 'больше всего жалоб' },
              { label: 'Категорий', value: district.problems.length, sub: 'типов проблем' },
            ].map(({ label, value, sub, color: c }) => (
              <div key={label} className="p-4 shadow-sm" style={card}>
                <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>{label}</p>
                <p className="text-2xl font-bold" style={{ color: c || 'var(--text)' }}>{value}</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>{sub}</p>
              </div>
            ))}
          </div>

          {(district.severityStat?.length > 0) && (
            <div className="p-5 shadow-sm" style={card}>
              <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--text)' }}>
                Распределение по тяжести
              </h2>
              <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>
                Классы ONNX: 0 — не инцидент … 4 — критическая
              </p>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={district.severityStat} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                  <XAxis
                    dataKey="label"
                    tick={{ fill: 'var(--muted)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    interval={0}
                    angle={-12}
                    textAnchor="end"
                    height={48}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fill: 'var(--muted)', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<SeverityTooltip />} cursor={{ fill: 'var(--bg-sub)' }} />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={48}>
                    {district.severityStat.map((row) => (
                      <Cell key={row.severity} fill={SEVERITY_COLORS[row.severity] ?? '#94a3b8'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {district.summary && (!taskId || isDemo || !loading) && (
        <div
          className="mx-4 lg:mx-5 mb-5 p-5 rounded-2xl flex gap-4 anim-up"
          style={{
            background: dark ? 'rgba(234,88,12,0.12)' : '#fff7ed',
            border: '2px solid rgba(234,88,12,0.4)',
          }}
        >
          <BotMessageSquare className="w-6 h-6 text-orange-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-bold text-orange-500 uppercase tracking-widest mb-2">Аналитическая сводка</p>
            <p className="text-base leading-relaxed font-medium" style={{ color: dark ? '#fed7aa' : '#9a3412' }}>
              {district.summary}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
