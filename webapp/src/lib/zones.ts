/** IANA zone -> place name plus the offset it is on right now, sorted west to east. */

const PLACES = [
  "Pacific/Pago_Pago",
  "Pacific/Honolulu",
  "America/Anchorage",
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/Mexico_City",
  "America/New_York",
  "America/Toronto",
  "America/Halifax",
  "America/Sao_Paulo",
  "America/Argentina/Buenos_Aires",
  "Atlantic/Reykjavik",
  "Europe/London",
  "Europe/Lisbon",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Madrid",
  "Europe/Rome",
  "Europe/Amsterdam",
  "Europe/Stockholm",
  "Europe/Warsaw",
  "Europe/Athens",
  "Europe/Istanbul",
  "Europe/Helsinki",
  "Africa/Lagos",
  "Africa/Johannesburg",
  "Africa/Cairo",
  "Africa/Nairobi",
  "Asia/Jerusalem",
  "Asia/Riyadh",
  "Asia/Dubai",
  "Asia/Tehran",
  "Asia/Karachi",
  "Asia/Kolkata",
  "Asia/Kathmandu",
  "Asia/Dhaka",
  "Asia/Yangon",
  "Asia/Bangkok",
  "Asia/Jakarta",
  "Asia/Ho_Chi_Minh",
  "Asia/Singapore",
  "Asia/Hong_Kong",
  "Asia/Shanghai",
  "Asia/Taipei",
  "Asia/Manila",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Australia/Perth",
  "Australia/Adelaide",
  "Australia/Sydney",
  "Australia/Brisbane",
  "Pacific/Auckland",
  "UTC",
] as const;

const LABELS: Record<string, string> = {
  "Pacific/Pago_Pago": "Pago Pago",
  "Pacific/Honolulu": "Honolulu",
  "America/Anchorage": "Anchorage",
  "America/Los_Angeles": "Los Angeles",
  "America/Denver": "Denver",
  "America/Chicago": "Chicago",
  "America/Mexico_City": "Mexico City",
  "America/New_York": "New York",
  "America/Toronto": "Toronto",
  "America/Halifax": "Halifax",
  "America/Sao_Paulo": "São Paulo",
  "America/Argentina/Buenos_Aires": "Buenos Aires",
  "Atlantic/Reykjavik": "Reykjavik",
  "Europe/London": "London",
  "Europe/Lisbon": "Lisbon",
  "Europe/Paris": "Paris",
  "Europe/Berlin": "Berlin",
  "Europe/Madrid": "Madrid",
  "Europe/Rome": "Rome",
  "Europe/Amsterdam": "Amsterdam",
  "Europe/Stockholm": "Stockholm",
  "Europe/Warsaw": "Warsaw",
  "Europe/Athens": "Athens",
  "Europe/Istanbul": "Istanbul",
  "Europe/Helsinki": "Helsinki",
  "Africa/Lagos": "Lagos",
  "Africa/Johannesburg": "Johannesburg",
  "Africa/Cairo": "Cairo",
  "Africa/Nairobi": "Nairobi",
  "Asia/Jerusalem": "Jerusalem",
  "Asia/Riyadh": "Riyadh",
  "Asia/Dubai": "Dubai",
  "Asia/Tehran": "Tehran",
  "Asia/Karachi": "Karachi",
  "Asia/Kolkata": "Kolkata",
  "Asia/Kathmandu": "Kathmandu",
  "Asia/Dhaka": "Dhaka",
  "Asia/Yangon": "Yangon",
  "Asia/Bangkok": "Bangkok",
  "Asia/Jakarta": "Jakarta",
  "Asia/Ho_Chi_Minh": "Ho Chi Minh",
  "Asia/Singapore": "Singapore",
  "Asia/Hong_Kong": "Hong Kong",
  "Asia/Shanghai": "Shanghai",
  "Asia/Taipei": "Taipei",
  "Asia/Manila": "Manila",
  "Asia/Tokyo": "Tokyo",
  "Asia/Seoul": "Seoul",
  "Australia/Perth": "Perth",
  "Australia/Adelaide": "Adelaide",
  "Australia/Sydney": "Sydney",
  "Australia/Brisbane": "Brisbane",
  "Pacific/Auckland": "Auckland",
  UTC: "UTC",
};

/** Current UTC offset in minutes. DST-aware, because it asks the platform. */
export function offsetMinutes(zone: string, at: Date = new Date()): number {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: zone,
      timeZoneName: "longOffset",
    }).formatToParts(at);
    const name = parts.find((p) => p.type === "timeZoneName")?.value ?? "GMT";
    const m = name.match(/GMT([+-])(\d{2}):?(\d{2})?/);
    if (!m) return 0;
    const sign = m[1] === "-" ? -1 : 1;
    return sign * (parseInt(m[2], 10) * 60 + parseInt(m[3] ?? "0", 10));
  } catch {
    return 0;
  }
}

/** "+08:00", "-05:00", "UTC". */
export function formatOffset(minutes: number): string {
  if (minutes === 0) return "UTC";
  const sign = minutes < 0 ? "-" : "+";
  const abs = Math.abs(minutes);
  const h = String(Math.floor(abs / 60)).padStart(2, "0");
  const m = String(abs % 60).padStart(2, "0");
  return `${sign}${h}:${m}`;
}

export type Zone = { id: string; label: string; offset: number };

/** Every entry, sorted by live offset from -12 to +14, then by name. */
export function zones(at: Date = new Date()): Zone[] {
  return PLACES.map((id) => ({
    id,
    label: LABELS[id] ?? id.split("/").pop()!.replace(/_/g, " "),
    offset: offsetMinutes(id, at),
  })).sort((a, b) => a.offset - b.offset || a.label.localeCompare(b.label));
}

export function zoneLabel(tz: string): string {
  if (LABELS[tz]) return LABELS[tz];
  const city = tz.split("/").pop() ?? tz;
  return city.replace(/_/g, " ");
}

export function zoneDisplay(tz: string, at: Date = new Date()): string {
  return `${zoneLabel(tz)} ${formatOffset(offsetMinutes(tz, at))}`;
}
