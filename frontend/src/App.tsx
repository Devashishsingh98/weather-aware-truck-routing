import { useEffect, useRef, useState } from "react"

import { loadHeatmap, planHaul } from "./api"
import { HeatmapControl } from "./components/HeatmapControl"
import { MapView } from "./components/MapView"
import { PlannerForm } from "./components/PlannerForm"
import { RouteList } from "./components/RouteList"
import { ScoringNotes } from "./components/ScoringNotes"
import { formatPounds, formatWhen, tomorrowAtEight } from "./format"
import { useDebounced } from "./useDebounced"
import type { FormState, HeatmapResponse, PlanResponse } from "./types"

export default function App() {
  const [form, setForm] = useState<FormState>(() => ({
    originQuery: "Dallas, TX",
    destinationQuery: "Denver, CO",
    departure: tomorrowAtEight(),
    load: "35000",
    interval: 25,
  }))
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null)
  const [heatmapLoading, setHeatmapLoading] = useState(false)
  const [heatmapError, setHeatmapError] = useState<string | null>(null)
  const [hour, setHour] = useState(0)
  const [showHeat, setShowHeat] = useState(true)
  const [editing, setEditing] = useState(true)
  const debouncedHour = useDebounced(hour, 40)
  const requestId = useRef(0)

  useEffect(() => {
    if (!editing) document.querySelector(".sidebar")?.scrollTo({ top: 0 })
  }, [editing, plan])

  async function submit(values: FormState) {
    const pounds = Number(values.load)
    if (!values.originQuery.trim() || !values.destinationQuery.trim()) {
      setError("Enter an origin and a destination.")
      return
    }
    if (!values.departure) {
      setError("Choose a departure date and time.")
      return
    }
    if (!Number.isFinite(pounds) || pounds <= 0 || pounds > 200_000) {
      setError("Enter a load weight between 1 and 200,000 lb.")
      return
    }
    const id = ++requestId.current
    setLoading(true)
    setError(null)
    setHeatmapError(null)
    try {
      const next = await planHaul({
        origin: placePayload(values.originQuery, values.origin),
        destination: placePayload(values.destinationQuery, values.destination),
        departure: values.departure,
        load_weight_lb: pounds,
        interval_miles: values.interval,
      })
      if (id !== requestId.current) return
      setPlan(next)
      setSelectedId(next.recommendation.route_id)
      setEditing(false)
      setHour(0)
      setHeatmap(null)
      setShowHeat(true)
      void fetchHeatmap(next, id)
    } catch (caught) {
      if (id !== requestId.current) return
      setError(caught instanceof Error ? caught.message : "The haul could not be planned.")
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }

  async function fetchHeatmap(next: PlanResponse, id: number) {
    setHeatmapLoading(true)
    try {
      const grid = await loadHeatmap({
        geometries: next.routes.map((route) => route.geometry.coordinates),
        departure: next.departure,
        load_weight_lb: next.load_weight_lb,
      })
      if (id !== requestId.current) return
      setHeatmap(grid)
    } catch (caught) {
      if (id !== requestId.current) return
      setHeatmapError(caught instanceof Error ? caught.message : "The corridor forecast could not be loaded.")
    } finally {
      if (id === requestId.current) setHeatmapLoading(false)
    }
  }

  function useSample() {
    const sample: FormState = {
      originQuery: "Dallas, TX",
      destinationQuery: "Denver, CO",
      departure: tomorrowAtEight(),
      load: "35000",
      interval: 25,
    }
    setForm(sample)
    void submit(sample)
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="28" height="28">
              <rect width="32" height="32" rx="7" fill="#e26a2c" />
              <path d="M6 22c5-1 7-9 11-9s3 5 9 3" fill="none" stroke="#1c2420" strokeWidth="2.2" strokeLinecap="round" />
              <circle cx="8" cy="21.2" r="1.8" fill="#1c2420" />
              <circle cx="24.5" cy="15.2" r="1.8" fill="#1c2420" />
            </svg>
          </span>
          <div>
            <p className="eyebrow">Safety dispatch</p>
            <h1>Weather-Aware Truck Routing</h1>
          </div>
        </div>
        <p className="topbar-note">
          {plan
            ? `${plan.origin.label.split(",")[0]} to ${plan.destination.label.split(",")[0]} · ${formatPounds(plan.load_weight_lb)} · ${formatWhen(plan.departure, plan.timezone)}`
            : "Three driving options, scored for wind, rain, snow, and the weight on the trailer."}
        </p>
      </header>
      <div className="shell">
        <aside className="sidebar">
          {plan && !editing ? (
            <div className="trip-summary">
              <div>
                <p className="eyebrow">This haul</p>
                <h2>
                  {shortPlace(plan.origin.label)} → {shortPlace(plan.destination.label)}
                </h2>
                <p>
                  {formatWhen(plan.departure, plan.timezone)} · {formatPounds(plan.load_weight_lb)} · every{" "}
                  {plan.interval_miles} miles
                </p>
              </div>
              <button className="button ghost" type="button" onClick={() => setEditing(true)}>
                Edit
              </button>
            </div>
          ) : (
            <PlannerForm
              form={form}
              loading={loading}
              onChange={setForm}
              onSubmit={(values) => void submit(values)}
              onSample={useSample}
            />
          )}
          {error ? (
            <p className="banner" role="alert">
              {error}
            </p>
          ) : null}
          {plan ? (
            <RouteList plan={plan} selectedId={selectedId ?? plan.recommendation.route_id} onSelect={setSelectedId} />
          ) : null}
          {plan ? (
            <HeatmapControl
              heatmap={heatmap}
              loading={heatmapLoading}
              error={heatmapError}
              hour={hour}
              timeZone={plan.timezone}
              visible={showHeat}
              onHour={setHour}
              onVisible={setShowHeat}
            />
          ) : null}
          <ScoringNotes />
        </aside>
        <MapView
          plan={plan}
          selectedId={selectedId}
          onSelect={setSelectedId}
          heatmap={heatmap}
          heatmapHour={Math.min(debouncedHour, heatmap ? heatmap.hours.length - 1 : debouncedHour)}
          showHeat={showHeat}
          loading={loading}
        />
      </div>
    </div>
  )
}

function shortPlace(label: string): string {
  return label.split(",")[0] ?? label
}

function placePayload(query: string, picked: FormState["origin"]) {
  if (picked && picked.label === query) {
    return { query, label: picked.label, lat: picked.lat, lon: picked.lon }
  }
  return { query }
}
