// Shared modal chrome - backdrop + centered card + close button.
export default function Modal({ title, onClose, children, wide }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className={`card w-full ${wide ? 'max-w-2xl' : 'max-w-md'} max-h-[85vh] overflow-y-auto p-6 rise`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          <button onClick={onClose} className="text-ink-dim hover:text-ink text-xl leading-none">&times;</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs text-ink-dim">{label}</label>
      {children}
    </div>
  )
}

export const inputCls = 'w-full px-3 py-2 rounded-lg bg-panel border border-edge text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition'
export const btnPrimary = 'px-4 py-2 rounded-lg grad text-white text-sm font-medium hover:opacity-90 transition disabled:opacity-40'
export const btnSecondary = 'px-4 py-2 rounded-lg bg-panel border border-edge text-ink text-sm hover:border-edge-bright transition'
export const btnDanger = 'text-xs text-bad hover:bg-bad/10 rounded px-2 py-1 transition'
