import { formatDuration, formatMiles } from "../format"
import { ROUTE_COLORS, riskFill } from "../risk"
import type { PlanResponse, RiskLabel, RouteOption } from "../types"

interface RouteListProps {
  plan: PlanResponse
  selectedId: string
  onSelect: (routeId: string) => void
}

export function RouteList({ plan, selectedId, onSelect }: RouteListProps) {
  return (
    <section className="results" aria-label="Route options">
      <div className={plan.recommendation.disqualified ? "callout is-blocked" : "callout"}>
        <p className="eyebrow">{plan.recommendation.disqualified ? "No clear corridor" : "Recommended"}</p>
        <p>{plan.recommendation.reason}</p>
      </div>
      {plan.route_note ? <p className="note">{plan.route_note}</p> : null}
      {plan.warnings.map((warning) => (
        <p className="note" key={warning}>
          {warning}
        </p>
      ))}
      <ol className="route-list">
        {plan.routes.map((route, index) => (
          <li key={route.id}>
            <button
              type="button"
              className={route.id === selectedId ? "route-card is-selected" : "route-card"}
              style={{ borderLeftColor: ROUTE_COLORS[index] ?? ROUTE_COLORS[0] }}
              onClick={() => onSelect(route.id)}
            >
              <header>
                <div>
                  <p className="route-kicker">
                    Rank {route.rank}
                    {route.recommended ? <span className="pill">Recommended</span> : null}
                    {route.metrics.disqualified ? <span className="pill is-blocked">No Travel</span> : null}
                  </p>
                  <h2>{route.name}</h2>
                  <p className="route-source">{sourceLabel(route)}</p>
                </div>
                <p className="route-time">
                  <strong>{formatDuration(route.duration_seconds)}</strong>
                  <span>{formatMiles(route.distance_miles)}</span>
                </p>
              </header>
              <RiskBar route={route} />
              <dl className="metric-grid">
                <Metric label="No Travel" value={route.metrics.no_travel_miles} />
                <Metric label="Severe" value={route.metrics.severe_miles} />
                <Metric label="High" value={route.metrics.high_miles} />
                <Metric label="Avg risk" value={route.metrics.average_risk} digits />
              </dl>
              <p className="checkpoint-count">
                {route.checkpoints.length} checkpoints · every {plan.interval_miles} miles
              </p>
            </button>
          </li>
        ))}
      </ol>
    </section>
  )
}

function RiskBar({ route }: { route: RouteOption }) {
  const parts: { level: RiskLabel; miles: number }[] = [
    { level: "Low", miles: route.metrics.low_miles },
    { level: "Moderate", miles: route.metrics.moderate_miles },
    { level: "High", miles: route.metrics.high_miles },
    { level: "Severe", miles: route.metrics.severe_miles },
    { level: "No Travel", miles: route.metrics.no_travel_miles },
  ]
  const total = parts.reduce((sum, part) => sum + part.miles, 0) || 1
  return (
    <div className="risk-bar" title={parts.map((part) => `${part.level} ${formatMiles(part.miles)}`).join(", ")}>
      {parts.map((part) =>
        part.miles > 0 ? (
          <span
            key={part.level}
            style={{ width: `${(part.miles / total) * 100}%`, background: riskFill(part.level) }}
          />
        ) : null,
      )}
    </div>
  )
}

function Metric({ label, value, digits = false }: { label: string; value: number; digits?: boolean }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{digits ? value.toFixed(2) : formatMiles(value)}</dd>
    </div>
  )
}

function sourceLabel(route: RouteOption): string {
  if (route.source === "via") {
    return route.via_label ? `Via waypoint · ${route.via_label.toLowerCase()} offset` : "Via waypoint"
  }
  return route.rank === 1 ? "OSRM driving" : "OSRM alternative"
}
