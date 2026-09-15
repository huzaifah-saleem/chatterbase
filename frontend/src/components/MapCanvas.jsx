// Leaflet point map: plots geo points as circle markers, sized by an
// optional value, auto-fit to the data's bounds. Same create-once/
// destroy-on-change lifecycle discipline as ChartCanvas.jsx - Leaflet has
// no clean "swap all data in place" API either, so destroy-and-recreate on
// any prop change stays consistent with the rest of this app.
import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Standard OSM raster tiles - free, no API key or account required (unlike
// CARTO's basemap tiles, which now gate on a registered referer/key even
// for local dev - verified live: curl got a real tile, a browser got an
// "API KEY REQUIRED" watermark tile back instead). Dimmed via CSS filter on
// the container (see .leaflet-tile-pane below) to sit better in this app's
// dark UI without needing a themed tile provider.
const TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const ACCENT = '#f27340'

export default function MapCanvas({ points = [], height = 320 }) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return
    const map = L.map(containerRef.current, { zoomControl: true })
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map)

    const valid = points.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng))
    if (valid.length === 0) {
      map.setView([20, 0], 2)
    } else {
      const values = valid.map((p) => (Number.isFinite(p.value) ? p.value : 1))
      const maxV = Math.max(...values, 1)
      const minV = Math.min(...values, 0)
      valid.forEach((p) => {
        const v = Number.isFinite(p.value) ? p.value : 1
        const radius = 6 + (maxV > minV ? ((v - minV) / (maxV - minV)) * 18 : 0)
        const label = p.label || `${p.lat.toFixed(3)}, ${p.lng.toFixed(3)}`
        L.circleMarker([p.lat, p.lng], {
          radius,
          color: ACCENT,
          weight: 1.5,
          fillColor: ACCENT,
          fillOpacity: 0.55,
        }).addTo(map).bindTooltip(Number.isFinite(p.value) ? `${label}: ${p.value}` : label)
      })
      map.fitBounds(L.latLngBounds(valid.map((p) => [p.lat, p.lng])).pad(0.25), { maxZoom: 12 })
    }

    return () => map.remove()
  }, [JSON.stringify(points)])

  return <div ref={containerRef} style={{ height, borderRadius: '10px', overflow: 'hidden' }} />
}
