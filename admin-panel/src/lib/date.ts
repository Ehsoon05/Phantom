const TEHRAN_TIME_ZONE = "Asia/Tehran";

const MONTHS = [
  "ژانویه",
  "فوریه",
  "مارس",
  "آوریل",
  "مه",
  "ژوئن",
  "جولای",
  "اوت",
  "سپتامبر",
  "اکتبر",
  "نوامبر",
  "دسامبر",
];

function normalizeDate(value: string | null | undefined) {
  if (!value) return null;
  return /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
}

export function formatTehranDateTime(value: string | null | undefined, includeTime = true) {
  const normalized = normalizeDate(value);
  if (!normalized) return "نامشخص";
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "نامشخص";

  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: includeTime ? "2-digit" : undefined,
    minute: includeTime ? "2-digit" : undefined,
    hourCycle: "h23",
    timeZone: TEHRAN_TIME_ZONE,
  }).formatToParts(date);
  const valueOf = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  const day = Number(valueOf("day"));
  const month = Number(valueOf("month"));
  const year = valueOf("year");
  const dateText = `${day} ${MONTHS[month - 1] ?? valueOf("month")} ${year}`;
  if (!includeTime) return dateText;
  return `${dateText}، ${valueOf("hour")}:${valueOf("minute")}`;
}
