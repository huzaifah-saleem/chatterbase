// A titled chart with a type-switcher strip, used both standalone (chat/task
// result blocks) and pinned-in-dashboard (with onTypeChange persisting via
// PUT .../charts/<id>, onUnpin removing it - both optional). `fill`/
// `dragHandle` are for DashboardsView.jsx's resizable grid - `fill` makes
// the chart stretch to the grid cell's own height (via ChartCanvas/
// MapCanvas/FlowMapCanvas's existing height prop, which already accepts a
// CSS size string, not just a pixel number) instead of a fixed height, and
// `dragHandle` renders a grip so react-grid-layout can scope dragging to
// just that handle - the chart body (map pan/zoom, type-switcher clicks)
// stays fully interactive without starting a drag.
import { useState } from 'react'
import { BarChart3, LineChart, PieChart, Circle, Radar as RadarIcon, MapPin, GripVertical } from 'lucide-react'
import ChartCanvas, { CHART_TYPES } from './ChartCanvas'
import MapCanvas from './MapCanvas'
import FlowMapCanvas from './FlowMapCanvas'

const ICONS = { bar: BarChart3, line: LineChart, pie: PieChart, doughnut: Circle, radar: RadarIcon }
const MAP_TYPES = ['map', 'od_map'] // geospatial - not interchangeable with the bar/line/pie/etc switcher

export default function ChartCard({ chart, onTypeChange, onUnpin, onPin, fill, dragHandle }) {
  const [type, setType] = useState(chart.type || 'bar')
  const isMap = MAP_TYPES.includes(chart.type)

  const handleType = (t) => {
    setType(t)
    onTypeChange?.(t)
  }

  return (
    <div className={`card p-4 rise ${fill ? 'h-full flex flex-col' : ''}`}>
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          {dragHandle && <span className="chart-drag-handle cursor-grab text-ink-faint hover:text-ink-dim shrink-0"><GripVertical size={14} /></span>}
          <h4 className="text-sm font-semibold text-ink truncate">{chart.title}</h4>
        </div>
        {!isMap && (
          <div className="flex gap-1">
            {CHART_TYPES.map((t) => {
              const Icon = ICONS[t]
              return (
                <button
                  key={t}
                  onClick={() => handleType(t)}
                  title={t}
                  className={`w-6 h-6 rounded flex items-center justify-center transition
                    ${type === t ? 'bg-accent text-white' : 'text-ink-dim hover:bg-edge hover:text-ink'}`}
                >
                  <Icon size={13} strokeWidth={1.75} />
                </button>
              )
            })}
          </div>
        )}
      </div>
      <div className={fill ? 'flex-1 min-h-0' : ''}>
        {chart.type === 'map' && <MapCanvas points={chart.points} height={fill ? '100%' : undefined} />}
        {chart.type === 'od_map' && <FlowMapCanvas flows={chart.flows} height={fill ? '100%' : undefined} />}
        {!isMap && <ChartCanvas type={type} title={chart.title} labels={chart.labels} data={chart.data} colors={chart.colors} height={fill ? '100%' : undefined} />}
      </div>
      {(onPin || onUnpin) && (
        <div className="mt-3 flex justify-end gap-2">
          {onPin && (
            <button onClick={onPin} className="text-xs px-3 py-1.5 rounded-lg bg-edge hover:bg-edge-bright text-ink transition flex items-center gap-1.5">
              <MapPin size={13} /> Pin to dashboard
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
