import type { RiskLabel } from "./types"

export const ROUTE_COLORS = ["#1d4e89", "#0f6e6e", "#a15c07"] as const

export const RISK_RGB = [
  "47, 125, 87",
  "184, 134, 11",
  "210, 105, 30",
  "194, 59, 59",
  "109, 40, 217",
] as const

export function riskColor(level: RiskLabel): string {
  switch (level) {
    case "Low":
      return "#1f6b48"
    case "Moderate":
      return "#8a5b00"
    case "High":
      return "#b45309"
    case "Severe":
      return "#a12626"
    case "No Travel":
      return "#5b21b6"
    default: {
      const unexpected: never = level
      return unexpected
    }
  }
}

export function riskFill(level: RiskLabel): string {
  switch (level) {
    case "Low":
      return "#2f7d57"
    case "Moderate":
      return "#d4a017"
    case "High":
      return "#e07a2f"
    case "Severe":
      return "#d64545"
    case "No Travel":
      return "#6d28d9"
    default: {
      const unexpected: never = level
      return unexpected
    }
  }
}

export function riskLabelFromScore(score: number): RiskLabel {
  const band = clampScore(score)
  switch (band) {
    case 0:
      return "Low"
    case 1:
      return "Moderate"
    case 2:
      return "High"
    case 3:
      return "Severe"
    case 4:
      return "No Travel"
    default: {
      const unexpected: never = band
      return unexpected
    }
  }
}

function clampScore(score: number): 0 | 1 | 2 | 3 | 4 {
  if (score >= 4) return 4
  if (score >= 3) return 3
  if (score >= 2) return 2
  if (score >= 1) return 1
  return 0
}
