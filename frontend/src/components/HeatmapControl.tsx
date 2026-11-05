import { formatWhen } from "../format"
import { riskColor, riskLabelFromScore } from "../risk"
import type { HeatmapResponse } from "../types"

interface HeatmapControlProps {
  heatmap: HeatmapResponse | null
  loading: boolean
  error: string | null
  hour: number
  timeZone: string
  visible: boolean
  onHour: (hour: number) => void
  onVisible: (visible: boolean) => void
}

export function HeatmapControl({
  heatmap,
  loading,
  error,
  hour,
  timeZone,
  visible,
  onHour,
  onVisible,
}: HeatmapControlProps) {
  const maxHour = heatmap ? Math.max(0, heatmap.hours.length - 1) : 48
  const stamp = heatmap?.hours[hour]
  const peak = heatmap ? peakScore(heatmap, hour) : 0
  const peakLabel = riskLabelFromScore(peak)

  return (
    <section className="heatmap-control" aria-label="Corridor forecast">
      <div className="heatmap-head">
        <div>
          <p className="eyebrow">Corridor forecast</p>
          <h2>Next 48 hours</h2>
        </div>
        <label className="toggle">
          <input
            type="checkbox"
            checked={visible}
            onChange={(event) => onVisible(event.target.checked)}
            disabled={!heatmap}
          />
          Show on map
        </label>
      </div>
      {loading ? <p className="note">Fetching the 48-hour grid once. The slider then stays on this page.</p> : null}
      {error ? <p className="note is-error">{error}</p> : null}
      <label className="slider-field">
        <span className="slider-readout">
          <strong>Hour {hour}</strong>
          {stamp ? <span>{formatWhen(stamp, timeZone)}</span> : <span>Waiting for the grid</span>}
        </span>
        <input
          type="range"
          min={0}
          max={maxHour}
          step={1}
          value={Math.min(hour, maxHour)}
          disabled={!heatmap}
          aria-valuetext={stamp ? formatWhen(stamp, timeZone) : `Hour ${hour}`}
          onChange={(event) => onHour(Number(event.target.value))}
        />
      </label>
      {heatmap ? (
        <p className="peak">
          Corridor peak at this hour:{" "}
          <strong style={{ color: riskColor(peakLabel) }}>{peakLabel}</strong>
        </p>
      ) : null}
    </section>
  )
}

function peakScore(heatmap: HeatmapResponse, hour: number): number {
  let peak = 0
  for (const point of heatmap.points) {
    const value = point.risk[hour] ?? 0
    if (value > peak) peak = value
  }
  return peak
}
