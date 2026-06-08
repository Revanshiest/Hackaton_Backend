import { useState, useCallback } from 'react'
import { Upload, FileSpreadsheet, Zap, ArrowRight, AlertCircle } from 'lucide-react'
import ThemeToggle from '../components/ThemeToggle'
import { api } from '../api/client'

export default function UploadScreen({ onUploadStarted, onDemoStart, dark, onToggleTheme }) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) {
      setFile(f)
      setError('')
    }
  }, [])

  const handleStart = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const res = await api.uploadDataset(file)
      onUploadStarted(res.task_id)
    } catch (err) {
      setError(err.message || 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex justify-end p-4">
        <ThemeToggle dark={dark} onToggle={onToggleTheme} />
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-4 pb-16 anim-fade">
        <div className="mb-12 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-red-600 shadow-lg mb-5">
            <Zap className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight mb-2" style={{ color: 'var(--text)' }}>
            ZeroProblems
          </h1>
          <p className="text-sm tracking-widest uppercase font-medium" style={{ color: 'var(--muted)' }}>
            Аналитика обращений граждан
          </p>
        </div>

        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onClick={() => document.getElementById('file-input').click()}
          className="w-full max-w-md rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all duration-200"
          style={{
            background: dragging ? 'rgba(220,38,38,0.05)' : file ? 'rgba(16,185,129,0.05)' : 'var(--bg-card)',
            borderColor: dragging ? '#dc2626' : file ? '#10b981' : 'var(--border)',
          }}
        >
          <input
            id="file-input"
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={(e) => {
              if (e.target.files[0]) {
                setFile(e.target.files[0])
                setError('')
              }
            }}
          />

          {file ? (
            <>
              <div className="w-14 h-14 rounded-xl bg-emerald-100 flex items-center justify-center mx-auto mb-4">
                <FileSpreadsheet className="w-7 h-7 text-emerald-600" />
              </div>
              <p className="font-semibold" style={{ color: 'var(--text)' }}>{file.name}</p>
              <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
                {(file.size / 1024).toFixed(1)} КБ · Готово
              </p>
            </>
          ) : (
            <>
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-4"
                style={{ background: 'var(--bg-sub)' }}
              >
                <Upload
                  className={`w-7 h-7 ${dragging ? 'text-red-500' : ''}`}
                  style={!dragging ? { color: 'var(--muted)' } : {}}
                />
              </div>
              <p className="font-semibold mb-1" style={{ color: 'var(--text)' }}>Перетащите Excel файл</p>
              <p className="text-sm" style={{ color: 'var(--muted)' }}>или кликните · .xlsx .xls</p>
            </>
          )}
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 text-sm text-red-600 max-w-md">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="mt-8 flex flex-col items-center gap-3">
          <button
            onClick={handleStart}
            disabled={!file || loading}
            className="flex items-center gap-2 px-8 py-3 rounded-xl font-semibold text-sm transition-all duration-200 active:scale-95"
            style={
              file && !loading
                ? { background: '#dc2626', color: '#fff', boxShadow: '0 4px 14px rgba(220,38,38,0.3)' }
                : { background: 'var(--bg-sub)', color: 'var(--muted)', cursor: 'not-allowed' }
            }
          >
            {loading ? 'Загрузка…' : 'Начать анализ'} {file && !loading && <ArrowRight className="w-4 h-4" />}
          </button>
          {!file && (
            <button
              onClick={onDemoStart}
              className="text-xs transition-colors hover:text-red-500"
              style={{ color: 'var(--muted)' }}
            >
              Пропустить — demo режим
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
