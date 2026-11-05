import type { GeocodeResult, HeatmapResponse, PlanRequest, PlanResponse } from "./types"

const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "")

export async function searchPlaces(query: string): Promise<GeocodeResult[]> {
  const payload = await requestJson(`${base}/api/geocode/?q=${encodeURIComponent(query)}`, {
    timeoutMs: 12_000,
  })
  if (!payload || typeof payload !== "object" || !("results" in payload)) return []
  const results = (payload as { results?: unknown }).results
  if (!Array.isArray(results)) return []
  return results.filter(isPlace)
}

export async function planHaul(body: PlanRequest): Promise<PlanResponse> {
  const payload = await requestJson(`${base}/api/plan/`, {
    method: "POST",
    timeoutMs: 90_000,
    body: JSON.stringify(body),
  })
  if (!isPlan(payload)) {
    throw new Error("The planner returned an unexpected response.")
  }
  return payload
}

export async function loadHeatmap(body: {
  geometries: [number, number][][]
  departure: string
  load_weight_lb: number
}): Promise<HeatmapResponse> {
  const payload = await requestJson(`${base}/api/heatmap/`, {
    method: "POST",
    timeoutMs: 90_000,
    body: JSON.stringify(body),
  })
  if (!isHeatmap(payload)) {
    throw new Error("The corridor forecast returned an unexpected response.")
  }
  return payload
}

async function requestJson(
  url: string,
  options: { method?: string; body?: string; timeoutMs: number },
): Promise<unknown> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), options.timeoutMs)
  try {
    const response = await fetch(url, {
      method: options.method ?? "GET",
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
      body: options.body,
      signal: controller.signal,
    })
    const payload = await readBody(response)
    if (!response.ok) {
      throw new Error(detailOf(payload, "The request failed."))
    }
    return payload
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The request timed out. The routing service may be busy — try again.")
    }
    if (error instanceof Error) throw error
    throw new Error("Could not reach the routing API.")
  } finally {
    window.clearTimeout(timer)
  }
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return {}
  try {
    return JSON.parse(text) as unknown
  } catch {
    return {}
  }
}

function detailOf(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === "string" && detail.trim()) return detail
  }
  return fallback
}

function isPlace(value: unknown): value is GeocodeResult {
  if (!value || typeof value !== "object") return false
  const place = value as Partial<GeocodeResult>
  return typeof place.label === "string" && typeof place.lat === "number" && typeof place.lon === "number"
}

function isPlan(value: unknown): value is PlanResponse {
  return Boolean(value && typeof value === "object" && Array.isArray((value as PlanResponse).routes))
}

function isHeatmap(value: unknown): value is HeatmapResponse {
  if (!value || typeof value !== "object") return false
  const heatmap = value as Partial<HeatmapResponse>
  return Array.isArray(heatmap.hours) && Array.isArray(heatmap.points)
}
