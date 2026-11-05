export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (hours <= 0) return `${mins} min`
  return `${hours} h ${mins} min`
}

export function formatMiles(miles: number): string {
  if (Math.abs(miles) >= 100) return `${Math.round(miles)} mi`
  return `${miles.toFixed(1)} mi`
}

export function formatPounds(pounds: number): string {
  return `${Math.round(pounds).toLocaleString("en-US")} lb`
}

export function formatWhen(iso: string, timeZone: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone,
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(date)
  } catch {
    return date.toLocaleString()
  }
}

export function tomorrowAtEight(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  const pad = (value: number) => String(value).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T08:00`
}
