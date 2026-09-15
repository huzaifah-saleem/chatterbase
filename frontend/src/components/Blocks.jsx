// Generic renderer for the backend's block vocabulary: {type: "text"|"table"|
// "chart"}. A new agent capability never needs new frontend code as long as
// it emits blocks in this shape - the payoff of building this generically
// back in Phase 1.
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import ChartCard from './ChartCard'

export function Blocks({ blocks, onPinChart }) {
  if (!blocks || blocks.length === 0) return null
  return (
    <div className="flex flex-col gap-3">
      {blocks.map((b, i) => {
        if (b.type === 'text') return <div key={i} className="md text-sm text-ink"><ReactMarkdown remarkPlugins={[remarkGfm]}>{b.content || ''}</ReactMarkdown></div>
        if (b.type === 'table') return <TableBlock key={i} block={b} />
        if (b.type === 'chart') return <ChartCard key={i} chart={b.chart} onPin={onPinChart ? () => onPinChart(b.chart) : undefined} />
        return null
      })}
    </div>
  )
}

function TableBlock({ block }) {
  const columns = block.columns || []
  const rows = block.rows || []
  return (
    <div className="overflow-x-auto rounded-lg border border-edge">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-panel">
            {columns.map((c, i) => <th key={i} className="text-left px-3 py-2 text-ink-dim font-medium border-b border-edge">{String(c)}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri} className="border-b border-edge last:border-0">
              {r.map((c, ci) => <td key={ci} className="px-3 py-1.5 text-ink">{String(c)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
