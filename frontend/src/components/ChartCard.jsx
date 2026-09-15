// A titled chart with a type-switcher strip, used both standalone (chat/task
// result blocks) and pinned-in-dashboard (with onTypeChange persisting via
// PUT .../charts/<id>, onUnpin removing it - both optional).
import { useState } from 'react'
import ChartCanvas, { CHART_TYPES } from './ChartCanvas'

const ICONS = { bar: '▊', line: '📈', pie: '◔', doughnut: '◯', radar: '✦' }

export default function ChartCard({ chart, onTypeChange, onUnpin, onPin }) {
  const [type, setType] = useState(chart.type || 'bar')

  const handleType = (t) => {
    setType(t)
    onTypeChange?.(t)
  }

  return (
    <div className="card p-4 rise">
      <div className="flex items-start justify-between gap-3 mb-2">
        <h4 className="text-sm font-semibold text-ink">{chart.title}</h4>
        <div className="flex gap-1">
          {CHART_TYPES.map((t) => (
            <button
              key={t}
              onClick={() => handleType(t)}
              title={t}
              className={`w-6 h-6 rounded text-xs flex items-center justify-center transition
                ${type === t ? 'bg-accent text-white' : 'text-ink-dim hover:bg-edge hover:text-ink'}`}
            >
              {ICONS[t]}
            </button>
          ))}
        </div>
      </div>
      <ChartCanvas type={type} title={chart.title} labels={chart.labels} data={chart.data} colors={chart.colors} />
      {(onPin || onUnpin) && (
        <div className="mt-3 flex justify-end gap-2">
          {onPin && (
            <button onClick={onPin} className="text-xs px-3 py-1.5 rounded-lg bg-edge hover:bg-edge-bright text-ink transition">
              📌 Pin to dashboard
            </button>
          )}
          {onUnpin && (
            <button onClick={onUnpin} className="text-xs px-3 py-1.5 rounded-lg text-bad hover:bg-bad/10 transition">
              Unpin
            </button>
          )}
        </div>
      )}
    </div>
  )
}
