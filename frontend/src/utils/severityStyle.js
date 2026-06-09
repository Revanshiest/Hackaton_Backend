/** Стили уведомлений по классу тяжести ONNX (0–4). */

export const SEVERITY_META = {
  0: { label: 'Не инцидент', accent: '#64748b', bg: '#f1f5f9', border: '#cbd5e1' },
  1: { label: 'Низкая', accent: '#16a34a', bg: '#dcfce7', border: '#86efac' },
  2: { label: 'Средняя', accent: '#ea580c', bg: '#ffedd5', border: '#fdba74' },
  3: { label: 'Высокая', accent: '#dc2626', bg: '#fee2e2', border: '#fca5a5' },
  4: { label: 'Критическая', accent: '#7f1d1d', bg: '#fecaca', border: '#f87171' },
}

export function severityMeta(severity) {
  return SEVERITY_META[severity] ?? SEVERITY_META[2]
}
