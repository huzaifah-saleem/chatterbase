// Chart.js wrapper. Two rules earned the hard way in earlier phases and
// preserved here:
//   1. Destroy-and-recreate the Chart.js instance on any type/data change -
//      mutating .config.type in place leaves stale scale/layout state and
//      produces broken oversized canvases.
//   2. The wrapper needs line-height:0/overflow:hidden (.chart-wrap in
//      index.css) - a <canvas> is inline-baseline by default before Chart.js
//      sets display:block, leaving a phantom gap that can sit on top of
//      controls beneath it.
import { useEffect, useRef } from 'react'
import Chart from 'chart.js/auto'

const PALETTE = ['#f27340', '#4C8BF5', '#3ecf8e', '#f0546a', '#a970ff', '#00BCD4', '#f5b940', '#8d6e63']

export default function ChartCanvas({ type = 'bar', title, labels = [], data = [], colors, height = 220 }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!canvasRef.current) return
    if (chartRef.current) {
      chartRef.current.destroy()
      chartRef.current = null
    }
    const palette = colors && colors.length ? colors : PALETTE
    const isPie = type === 'pie' || type === 'doughnut'
    chartRef.current = new Chart(canvasRef.current, {
      type,
      data: {
        labels,
        datasets: [{
          label: title || '',
          data,
          backgroundColor: isPie ? labels.map((_, i) => palette[i % palette.length]) : palette[0] + 'cc',
          borderColor: isPie ? '#11151d' : palette[0],
          borderWidth: isPie ? 2 : 1,
          borderRadius: type === 'bar' ? 6 : 0,
          tension: type === 'line' ? 0.35 : 0,
          fill: type === 'line' ? false : undefined,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: isPie, labels: { color: '#8b94a7', boxWidth: 12, font: { size: 11 } } },
          title: { display: false },
        },
        scales: isPie ? {} : {
          x: { ticks: { color: '#8b94a7', font: { size: 11 } }, grid: { color: '#232a38' } },
          y: { ticks: { color: '#8b94a7', font: { size: 11 } }, grid: { color: '#232a38' }, beginAtZero: true },
        },
      },
    })
    return () => {
      if (chartRef.current) {
        chartRef.current.destroy()
        chartRef.current = null
      }
    }
  }, [type, title, JSON.stringify(labels), JSON.stringify(data), JSON.stringify(colors)])

  return (
    <div className="chart-wrap" style={{ height }}>
      <canvas ref={canvasRef} />
    </div>
  )
}

export const CHART_TYPES = ['bar', 'line', 'pie', 'doughnut', 'radar']
