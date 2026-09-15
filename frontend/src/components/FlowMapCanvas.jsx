// Leaflet origin-destination flow map: a curved line between each flow's
// origin/destination, weighted by an optional value, with circle markers
// at each endpoint. The curve is a plain quadratic Bezier through a
// perpendicular-offset midpoint - enough to visually separate overlapping
// flows without pulling in a curve plugin for one small effect.
import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// See MapCanvas.jsx for why this is plain OSM tiles, not CARTO's dark set.
const TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const ORIGIN_COLOR = '#3ecf8e'
const DEST_COLOR = '#f0546a'
const FLOW_COLOR = '#f27340'

function curvedPath([lat1, lng1], [lat2, lng2], bend = 0.15) {
  const mLat = (lat1 + lat2) / 2
  const mLng = (lng1 + lng2) / 2
  const dLat = lat2 - lat1
  const dLng = lng2 - lng1
  const ctrlLat = mLat - dLng * bend
  const ctrlLng = mLng + dLat * bend
  const steps = 24
  const pts = []
  for (let i = 0; i <= steps; i++) {
    const t = i / steps
    const lat = (1 - t) ** 2 * lat1 + 2 * (1 - t) * t * ctrlLat + t ** 2 * lat2
    const lng = (1 - t) ** 2 * lng1 + 2 * (1 - t) * t * ctrlLng + t ** 2 * lng2
    pts.push([lat, lng])
  }
  return pts
}

export default function FlowMapCanvas({ flows = [], height = 320 }) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return
    const map = L.map(containerRef.current, { zoomControl: true })
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map)

    const valid = flows.filter((f) =>
      [f.origin_lat, f.origin_lng, f.dest_lat, f.dest_lng].every(Number.isFinite))

    if (valid.length === 0) {
      map.setView([20, 0], 2)
    } else {
      const values = valid.map((f) => (Number.isFinite(f.value) ? f.value : 1))
      const maxV = Math.max(...values, 1)
      const minV = Math.min(...values, 0)
      const allLatLngs = []

      valid.forEach((f) => {
        const v = Number.isFinite(f.value) ? f.value : 1
        const weight = 1.5 + (maxV > minV ? ((v - minV) / (maxV - minV)) * 6 : 0)
        const origin = [f.origin_lat, f.origin_lng]
        const dest = [f.dest_lat, f.dest_lng]
        const label = `${f.origin_label || 'Origin'} → ${f.dest_label || 'Destination'}${Number.isFinite(f.value) ? `: ${f.value}` : ''}`

        L.polyline(curvedPath(origin, dest), { color: FLOW_COLOR, weight, opacity: 0.65 })
          .addTo(map).bindTooltip(label)
        L.circleMarker(origin, { radius: 5, color: ORIGIN_COLOR, fillColor: ORIGIN_COLOR, fillOpacity: 0.9, weight: 1 })
          .addTo(map).bindTooltip(f.origin_label || 'Origin')
        L.circleMarker(dest, { radius: 5, color: DEST_COLOR, fillColor: DEST_COLOR, fillOpacity: 0.9, weight: 1 })
          .addTo(map).bindTooltip(f.dest_label || 'Destination')
        allLatLngs.push(origin, dest)
      })

      map.fitBounds(L.latLngBounds(allLatLngs).pad(0.25), { maxZoom: 12 })
    }

    return () => map.remove()
  }, [JSON.stringify(flows)])

  return <div ref={containerRef} style={{ height, borderRadius: '10px', overflow: 'hidden' }} />
}
