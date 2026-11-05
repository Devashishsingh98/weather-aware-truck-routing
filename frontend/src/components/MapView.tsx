import { useEffect, useRef } from "react"
import { CircleMarker, MapContainer, Polyline, Popup, ScaleControl, TileLayer, useMap } from "react-leaflet"
import { DomUtil, type Map as LeafletMap } from "leaflet"

import { formatMiles, formatWhen } from "../format"
import { RISK_RGB, ROUTE_COLORS, riskColor, riskFill } from "../risk"
import type { Checkpoint, HeatmapResponse, PlanResponse, RiskLabel, RouteOption } from "../types"

interface MapViewProps {
  plan: PlanResponse | null
  selectedId: string | null
  onSelect: (routeId: string) => void
  heatmap: HeatmapResponse | null
  heatmapHour: number
  showHeat: boolean
  loading: boolean
}

export function MapView({ plan, selectedId, onSelect, heatmap, heatmapHour, showHeat, loading }: MapViewProps) {
  const selected = plan?.routes.find((route) => route.id === selectedId) ?? plan?.routes[0]
  return (
    <div className="map-pane">
      <MapContainer
        center={[39.5, -98.35]}
        zoom={4}
        minZoom={3}
        scrollWheelZoom
        className="map-canvas"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        <ScaleControl position="bottomright" imperial metric={false} />
        {plan ? <FitToRoutes plan={plan} /> : null}
        {plan
          ? [...plan.routes]
              .sort((left, right) => drawOrder(left, right, selectedId))
              .map((route) => (
                <RouteShape
                  key={route.id}
                  route={route}
                  color={ROUTE_COLORS[plan.routes.findIndex((item) => item.id === route.id)] ?? ROUTE_COLORS[0]}
                  selected={route.id === selectedId}
                  timeZone={plan.timezone}
                  onSelect={onSelect}
                />
              ))
          : null}
        <RiskHeat points={heatmap?.points ?? []} hour={heatmapHour} visible={showHeat && Boolean(heatmap)} />
      </MapContainer>
      <aside className="map-legend">
        <p>Risk at ETA</p>
        <ul>
          {(["Low", "Moderate", "High", "Severe", "No Travel"] as RiskLabel[]).map((level) => (
            <li key={level}>
              <i style={{ background: riskFill(level) }} />
              {level}
            </li>
          ))}
        </ul>
        {plan ? (
          <ul className="route-legend">
            {plan.routes.map((route, index) => (
              <li key={route.id}>
                <i style={{ background: ROUTE_COLORS[index] ?? ROUTE_COLORS[0] }} />
                {route.name}
              </li>
            ))}
          </ul>
        ) : null}
      </aside>
      {selected ? (
        <div className="map-chip">
          <strong>{selected.name}</strong>
          <span>{formatMiles(selected.distance_miles)}</span>
        </div>
      ) : null}
      {!plan && !loading ? (
        <div className="map-empty">
          <p className="eyebrow">Nothing planned yet</p>
          <h2>Three corridors, scored before you roll.</h2>
          <p>Enter a haul. The map draws each option, colors every checkpoint by risk, and lays a 48-hour weather field over the corridor.</p>
        </div>
      ) : null}
      {loading ? (
        <div className="map-status" role="status">
          Routing three options and sampling wind, rain, and snow at each checkpoint.
        </div>
      ) : null}
    </div>
  )
}

function drawOrder(left: RouteOption, right: RouteOption, selectedId: string | null): number {
  if (left.id === selectedId) return 1
  if (right.id === selectedId) return -1
  return left.rank - right.rank
}

function FitToRoutes({ plan }: { plan: PlanResponse }) {
  const map = useMap()
  useEffect(() => {
    const latlngs = plan.routes.flatMap((route) =>
      route.geometry.coordinates.map(([lon, lat]) => [lat, lon] as [number, number]),
    )
    if (latlngs.length === 0) return
    map.fitBounds(latlngs, { padding: [36, 36] })
  }, [map, plan.routes])
  return null
}

function RouteShape({
  route,
  color,
  selected,
  timeZone,
  onSelect,
}: {
  route: RouteOption
  color: string
  selected: boolean
  timeZone: string
  onSelect: (routeId: string) => void
}) {
  const positions = route.geometry.coordinates.map(([lon, lat]) => [lat, lon] as [number, number])
  return (
    <>
      <Polyline
        positions={positions}
        pathOptions={{ color: "#fffdf8", weight: selected ? 11 : 7, opacity: selected ? 0.95 : 0.45 }}
        interactive={false}
      />
      <Polyline
        positions={positions}
        pathOptions={{ color, weight: selected ? 5.5 : 3.5, opacity: selected ? 0.95 : 0.55 }}
        eventHandlers={{ click: () => onSelect(route.id) }}
      />
      {route.checkpoints.map((checkpoint) => (
        <CircleMarker
          key={`${route.id}-${checkpoint.mile}`}
          center={[checkpoint.lat, checkpoint.lon]}
          radius={selected ? 7 : 4.5}
          pathOptions={{
            color: "#fffdf8",
            weight: 1.5,
            fillColor: riskFill(checkpoint.risk),
            fillOpacity: selected ? 0.95 : 0.72,
          }}
          eventHandlers={{ click: () => onSelect(route.id) }}
        >
          <Popup>
            <CheckpointPopup checkpoint={checkpoint} routeName={route.name} timeZone={timeZone} />
          </Popup>
        </CircleMarker>
      ))}
    </>
  )
}

function CheckpointPopup({
  checkpoint,
  routeName,
  timeZone,
}: {
  checkpoint: Checkpoint
  routeName: string
  timeZone: string
}) {
  return (
    <div className="popup">
      <p className="eyebrow">{routeName}</p>
      <h3>
        Mile {formatMiles(checkpoint.mile).replace(" mi", "")}
        <span style={{ color: riskColor(checkpoint.risk) }}>{checkpoint.risk}</span>
      </h3>
      <p>ETA {formatWhen(checkpoint.eta, timeZone)}</p>
      <ul>
        <li>Wind {checkpoint.wind_mph.toFixed(1)} mph · {checkpoint.wind_risk_after_load}</li>
        <li>Rain {checkpoint.rain_in_hr.toFixed(2)} in/hr · {checkpoint.rain_risk}</li>
        <li>Snow {checkpoint.snow_in_hr.toFixed(2)} in/hr · {checkpoint.snow_risk}</li>
      </ul>
      <p>{factorSentence(checkpoint)}</p>
      {checkpoint.load_note ? <p className="popup-note">{checkpoint.load_note}</p> : null}
      {checkpoint.imputed ? <p className="popup-note">A missing forecast hour was scored as calm.</p> : null}
      {checkpoint.clamped ? <p className="popup-note">This ETA sits outside the forecast window.</p> : null}
    </div>
  )
}

function factorSentence(checkpoint: Checkpoint): string {
  if (checkpoint.risk === "Low") return "Wind, rain, and snow are all Low."
  if (checkpoint.factors.length === 0) return "Risk is set by the worst condition."
  return `Set by ${checkpoint.factors.join(" and ")}.`
}

function RiskHeat({
  points,
  hour,
  visible,
}: {
  points: HeatmapResponse["points"]
  hour: number
  visible: boolean
}) {
  const map = useMap()
  const drawRef = useRef<() => void>(() => {})
  const dataRef = useRef({ points, hour, visible })

  useEffect(() => {
    const pane = ensureHeatPane(map)
    const canvas = DomUtil.create("canvas", "risk-heat-canvas", pane) as HTMLCanvasElement
    const frame = { id: 0 }
    const draw = () => {
      paintHeat(map, canvas, dataRef.current)
    }
    drawRef.current = draw
    const schedule = () => {
      window.cancelAnimationFrame(frame.id)
      frame.id = window.requestAnimationFrame(draw)
    }
    schedule()
    map.on("move zoom viewreset resize", schedule)
    return () => {
      window.cancelAnimationFrame(frame.id)
      map.off("move zoom viewreset resize", schedule)
      canvas.remove()
      drawRef.current = () => {}
    }
  }, [map])

  useEffect(() => {
    dataRef.current = { points, hour, visible }
    drawRef.current()
  }, [points, hour, visible])

  return null
}

function ensureHeatPane(map: LeafletMap): HTMLElement {
  const existing = map.getPane("heat")
  if (existing) return existing
  const pane = map.createPane("heat")
  pane.style.zIndex = "350"
  pane.style.pointerEvents = "none"
  return pane
}

function paintHeat(
  map: LeafletMap,
  canvas: HTMLCanvasElement,
  data: { points: HeatmapResponse["points"]; hour: number; visible: boolean },
) {
  const size = map.getSize()
  const ratio = window.devicePixelRatio || 1
  canvas.width = Math.max(1, size.x * ratio)
  canvas.height = Math.max(1, size.y * ratio)
  canvas.style.width = `${size.x}px`
  canvas.style.height = `${size.y}px`
  DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]))
  const context = canvas.getContext("2d")
  if (!context) return
  context.setTransform(ratio, 0, 0, ratio, 0, 0)
  context.clearRect(0, 0, size.x, size.y)
  if (!data.visible || data.points.length === 0) return

  const radius = blobRadius(map)
  const ordered = [...data.points].sort((left, right) => (left.risk[data.hour] ?? 0) - (right.risk[data.hour] ?? 0))
  for (const point of ordered) {
    const score = point.risk[data.hour] ?? 0
    const rgb = RISK_RGB[Math.max(0, Math.min(4, Math.round(score)))] ?? RISK_RGB[0]
    const spot = map.latLngToContainerPoint([point.lat, point.lon])
    const gradient = context.createRadialGradient(spot.x, spot.y, 0, spot.x, spot.y, radius)
    gradient.addColorStop(0, `rgba(${rgb}, 0.62)`)
    gradient.addColorStop(0.45, `rgba(${rgb}, 0.24)`)
    gradient.addColorStop(1, `rgba(${rgb}, 0)`)
    context.fillStyle = gradient
    context.beginPath()
    context.arc(spot.x, spot.y, radius, 0, Math.PI * 2)
    context.fill()
  }
}

function blobRadius(map: LeafletMap): number {
  const center = map.getCenter()
  const origin = map.latLngToContainerPoint(center)
  const east = map.latLngToContainerPoint([center.lat, center.lng + 22 / (69 * Math.cos((center.lat * Math.PI) / 180) || 1)])
  const pixels = Math.abs(east.x - origin.x)
  return Math.max(18, Math.min(110, pixels))
}
