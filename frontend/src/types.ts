export type RiskLabel = "Low" | "Moderate" | "High" | "Severe" | "No Travel"

export type IntervalMiles = 10 | 25 | 50

export interface PlaceInput {
  query?: string
  label?: string
  lat?: number
  lon?: number
}

export interface GeocodeResult {
  label: string
  lat: number
  lon: number
}

export interface PlanRequest {
  origin: PlaceInput
  destination: PlaceInput
  departure: string
  load_weight_lb: number
  interval_miles: IntervalMiles
}

export interface Checkpoint {
  mile: number
  lat: number
  lon: number
  eta: string
  wind_mph: number
  rain_in_hr: number
  snow_in_hr: number
  wind_risk: RiskLabel
  wind_risk_after_load: RiskLabel
  rain_risk: RiskLabel
  snow_risk: RiskLabel
  risk: RiskLabel
  load_note: string | null
  factors: string[]
  forecast_hour: string
  imputed: boolean
  clamped: boolean
}

export interface RouteMetrics {
  no_travel_miles: number
  severe_miles: number
  high_miles: number
  moderate_miles: number
  low_miles: number
  average_risk: number
  disqualified: boolean
}

export interface RouteOption {
  id: string
  name: string
  source: "osrm" | "via"
  via_label: string | null
  rank: number
  recommended: boolean
  distance_miles: number
  duration_seconds: number
  geometry: { type: "LineString"; coordinates: [number, number][] }
  checkpoints: Checkpoint[]
  metrics: RouteMetrics
}

export interface PlanResponse {
  origin: GeocodeResult
  destination: GeocodeResult
  departure: string
  timezone: string
  load_weight_lb: number
  interval_miles: number
  route_note: string | null
  warnings: string[]
  recommendation: {
    route_id: string
    disqualified: boolean
    reason: string
  }
  routes: RouteOption[]
}

export interface HeatPoint {
  lat: number
  lon: number
  risk: number[]
}

export interface HeatmapResponse {
  hours: string[]
  risk_labels: string[]
  points: HeatPoint[]
}

export interface FormState {
  originQuery: string
  origin?: GeocodeResult
  destinationQuery: string
  destination?: GeocodeResult
  departure: string
  load: string
  interval: IntervalMiles
}
