import { useEffect, useId, useState } from "react"
import type { FormEvent } from "react"

import { searchPlaces } from "../api"
import type { FormState, GeocodeResult, IntervalMiles } from "../types"

interface PlannerFormProps {
  form: FormState
  loading: boolean
  onChange: (form: FormState) => void
  onSubmit: (form: FormState) => void
  onSample: () => void
}

const INTERVALS: IntervalMiles[] = [10, 25, 50]

export function PlannerForm({ form, loading, onChange, onSubmit, onSample }: PlannerFormProps) {
  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    onSubmit(form)
  }

  return (
    <form className="planner" onSubmit={handleSubmit}>
      <PlaceField
        id="origin"
        label="Origin"
        value={form.originQuery}
        picked={form.origin}
        onText={(originQuery) => onChange({ ...form, originQuery, origin: undefined })}
        onPick={(place) => onChange({ ...form, originQuery: place.label, origin: place })}
      />
      <PlaceField
        id="destination"
        label="Destination"
        value={form.destinationQuery}
        picked={form.destination}
        onText={(destinationQuery) => onChange({ ...form, destinationQuery, destination: undefined })}
        onPick={(place) => onChange({ ...form, destinationQuery: place.label, destination: place })}
      />
      <label className="field">
        <span>Departure</span>
        <input
          type="datetime-local"
          value={form.departure}
          required
          onChange={(event) => onChange({ ...form, departure: event.target.value })}
        />
        <small>Clock time at the origin. A 08:00 departure in Dallas is 08:00 Central.</small>
      </label>
      <label className="field">
        <span>Load weight</span>
        <input
          type="number"
          min={1}
          max={200000}
          step="any"
          inputMode="numeric"
          value={form.load}
          required
          onChange={(event) => onChange({ ...form, load: event.target.value })}
        />
        <small>Pounds on the trailer. 45 mph and above gets stricter past 30,000 lb.</small>
      </label>
      <fieldset className="field">
        <legend>Checkpoint interval</legend>
        <div className="segmented" role="radiogroup" aria-label="Checkpoint interval">
          {INTERVALS.map((miles) => (
            <label key={miles} className={form.interval === miles ? "segment is-on" : "segment"}>
              <input
                type="radio"
                name="interval"
                value={miles}
                checked={form.interval === miles}
                onChange={() => onChange({ ...form, interval: miles })}
              />
              {miles} mi
            </label>
          ))}
        </div>
        <small>Weather is read at the truck's estimated arrival, then every {form.interval} miles.</small>
      </fieldset>
      <div className="form-actions">
        <button className="button primary" type="submit" disabled={loading}>
          {loading ? "Scoring corridors…" : "Plan haul"}
        </button>
        <button className="button ghost" type="button" onClick={onSample} disabled={loading}>
          Use Dallas → Denver, 35,000 lb
        </button>
      </div>
    </form>
  )
}

interface PlaceFieldProps {
  id: string
  label: string
  value: string
  picked?: GeocodeResult
  onText: (value: string) => void
  onPick: (place: GeocodeResult) => void
}

function PlaceField({ id, label, value, picked, onText, onPick }: PlaceFieldProps) {
  const listId = useId()
  const [match, setMatch] = useState<{ query: string; places: GeocodeResult[] } | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const [focused, setFocused] = useState(false)
  const settled = Boolean(picked && picked.label === value)
  const results = !settled && match?.query === value ? match.places : []
  const open = focused && !dismissed && results.length > 0

  useEffect(() => {
    if (!focused || settled || value.trim().length < 3) return
    let cancelled = false
    const handle = window.setTimeout(() => {
      searchPlaces(value)
        .then((places) => {
          if (!cancelled) setMatch({ query: value, places })
        })
        .catch(() => {
          if (!cancelled) setMatch({ query: value, places: [] })
        })
    }, 280)
    return () => {
      cancelled = true
      window.clearTimeout(handle)
    }
  }, [focused, settled, value])

  return (
    <label className="field place-field">
      <span>{label}</span>
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        placeholder={id === "origin" ? "Dallas, TX" : "Denver, CO"}
        value={value}
        required
        onChange={(event) => {
          setDismissed(false)
          onText(event.target.value)
        }}
        onFocus={() => {
          setFocused(true)
          setDismissed(false)
        }}
        onBlur={() => setFocused(false)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setDismissed(true)
        }}
      />
      {open && results.length > 0 ? (
        <ul id={listId} className="suggestions" role="listbox">
          {results.map((place) => (
            <li key={`${place.label}-${place.lat}-${place.lon}`}>
              <button
                type="button"
                role="option"
                onMouseDown={(event) => {
                  event.preventDefault()
                  onPick(place)
                  setDismissed(true)
                }}
              >
                {place.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </label>
  )
}
