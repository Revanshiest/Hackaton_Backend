import { useEffect, useState } from 'react'
import { CheckCircle2, Database, BrainCircuit, Layers, Tag, FileText, Zap, AlertCircle } from 'lucide-react'
import { demoPipelineSteps } from '../demo'
import { api } from '../api/client'

const STEP_ICONS = {
  load: Database,
  classify: BrainCircuit,
  aggregate: Layers,
  topics: Tag,
  summary: FileText,
  report: FileText,
}

const DEMO_STEP_MS = 1800

function stepIcon(id, idx) {
  return STEP_ICONS[id] || [Database, BrainCircuit, Layers, Tag, FileText][idx] || FileText
}

export default function ProgressScreen({ taskId, onDone, onReset }) {
  const [steps, setSteps] = useState(demoPipelineSteps.map((s) => ({ ...s, status: 'pending', detail: '' })))
  const [currentStep, setCurrentStep] = useState(0)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!taskId) {
      const steps = demoPipelineSteps
      const total = steps.length * DEMO_STEP_MS
      const iv = setInterval(() => setProgress((p) => Math.min(p + 100 / (total / 50), 100)), 50)
      const timers = steps.map((_, i) =>
        setTimeout(() => setCurrentStep(i + 1), (i + 1) * DEMO_STEP_MS),
      )
      const done = setTimeout(() => {
        clearInterval(iv)
        setProgress(100)
        setTimeout(onDone, 600)
      }, total + 300)
      return () => {
        clearInterval(iv)
        timers.forEach(clearTimeout)
        clearTimeout(done)
      }
    }

    let cancelled = false
    const poll = async () => {
      try {
        const job = await api.getJob(taskId)
        if (cancelled) return

        const apiSteps = job.steps || []
        if (apiSteps.length) {
          setSteps(
            apiSteps.map((s) => ({
              id: s.id,
              label: s.label,
              description: s.detail || '',
              status: s.status,
            })),
          )
          const doneCount = apiSteps.filter((s) => s.status === 'done').length
          const runningIdx = apiSteps.findIndex((s) => s.status === 'running')
          setCurrentStep(runningIdx >= 0 ? runningIdx + 1 : doneCount)
          setProgress(Math.min(100, Math.round((doneCount / apiSteps.length) * 100)))
        }

        if (job.status === 'completed') {
          setProgress(100)
          setCurrentStep(apiSteps.length)
          setTimeout(onDone, 500)
          return
        }
        if (job.status === 'failed') {
          setError(job.message || 'Ошибка обработки')
          return
        }
        setTimeout(poll, 1500)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Не удалось получить статус')
      }
    }

    poll()
    return () => { cancelled = true }
  }, [taskId, onDone])

  const displaySteps = taskId ? steps : demoPipelineSteps

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
      <div className="flex items-center gap-2 mb-14">
        <div className="w-7 h-7 rounded-lg bg-red-600 flex items-center justify-center">
          <Zap className="w-4 h-4 text-white" />
        </div>
        <span className="font-bold" style={{ color: 'var(--text)' }}>ZeroProblems</span>
      </div>

      <div className="w-full max-w-sm anim-up">
        <h2 className="text-xl font-bold text-center mb-1" style={{ color: 'var(--text)' }}>Анализ данных</h2>
        <p className="text-sm text-center mb-10" style={{ color: 'var(--muted)' }}>
          {taskId ? `Задача ${taskId}` : 'Demo — снимок реальных данных…'}
        </p>

        {error ? (
          <div className="text-center mb-6">
            <div className="flex items-start gap-2 text-sm text-red-600 justify-center mb-4">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span className="text-left break-words">{error}</span>
            </div>
            {onReset && (
              <button
                type="button"
                onClick={onReset}
                className="px-5 py-2.5 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors"
              >
                Начать заново
              </button>
            )}
          </div>
        ) : (
          <div className="relative">
            <div className="absolute left-5 top-5 bottom-5 w-0.5" style={{ background: 'var(--border)' }} />
            <div
              className="absolute left-5 top-5 w-0.5 bg-red-500 transition-all duration-700"
              style={{ height: `calc(${(currentStep / displaySteps.length) * 100}% - 20px)` }}
            />

            <div className="space-y-5">
              {displaySteps.map((step, idx) => {
                const Icon = stepIcon(step.id, idx)
                const done = taskId ? step.status === 'done' : idx < currentStep
                const active = taskId ? step.status === 'running' : idx === currentStep
                const failed = step.status === 'error'
                return (
                  <div key={step.id} className="flex items-start gap-4 relative">
                    <div
                      className={`relative z-10 w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 border-2 transition-all duration-500 ${active ? 'step-pulse' : ''}`}
                      style={{
                        background: done ? '#dc2626' : failed ? '#991b1b' : 'var(--bg-card)',
                        borderColor: done || failed ? '#dc2626' : active ? '#dc2626' : 'var(--border)',
                      }}
                    >
                      {done ? (
                        <CheckCircle2 className="w-5 h-5 text-white" />
                      ) : (
                        <Icon className="w-4 h-4" style={{ color: active || failed ? '#dc2626' : 'var(--muted)' }} />
                      )}
                    </div>
                    <div className="pt-1.5">
                      <p
                        className="text-sm font-semibold transition-colors duration-300"
                        style={{ color: done ? 'var(--muted)' : active ? 'var(--text)' : 'var(--muted)' }}
                      >
                        {step.label}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: active ? 'var(--text-2)' : 'var(--border)' }}>
                        {step.description || step.detail || ''}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {!error && (
          <div className="mt-10">
            <div className="flex justify-between text-xs mb-2" style={{ color: 'var(--muted)' }}>
              <span>Прогресс</span>
              <span className="font-medium" style={{ color: 'var(--text-2)' }}>{Math.round(progress)}%</span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-sub)' }}>
              <div className="h-full bg-red-600 rounded-full transition-all duration-200" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
