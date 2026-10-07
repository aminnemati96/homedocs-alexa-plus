import type { Notification } from "./api";

function ordinal(day: number): string {
  if (day % 100 >= 11 && day % 100 <= 13) return `${day}th`;
  return `${day}${["th", "st", "nd", "rd"][day % 10] ?? "th"}`;
}

function spokenDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  const name = new Date(year, month - 1, day).toLocaleString("en-US", { month: "long" });
  return `${name} ${ordinal(day)}`;
}

function spokenDistance(days: number): string {
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return `in ${days} days`;
}

/**
 * The spoken notification summary, built from data the page already has.
 * Like an Echo reading its notifications: no model call and no new lookup.
 */
export function describeNotifications(items: Notification[]): string {
  if (items.length === 0) return "You have no notifications. Nothing is due in the next two weeks.";
  const intro = items.length === 1 ? "You have one notification." : `You have ${items.length} notifications.`;
  const lines = items.map(
    (n) => `${n.title}: ${n.label.toLowerCase()} ${spokenDate(n.date)}, ${spokenDistance(n.days_away)}.`,
  );
  return [intro, ...lines].join(" ");
}
