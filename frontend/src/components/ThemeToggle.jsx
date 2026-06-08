import { Sun, Moon } from 'lucide-react'

export default function ThemeToggle({ dark, onToggle }) {
  return (
    <button
      onClick={onToggle}
      title={dark ? 'Светлая тема' : 'Тёмная тема'}
      className="w-8 h-8 flex items-center justify-center rounded-lg border transition-colors"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-2)' }}
    >
      {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  )
}
