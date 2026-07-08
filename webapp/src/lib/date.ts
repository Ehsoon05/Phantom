const TEHRAN_TIME_ZONE = "Asia/Tehran";
const LTR_MARK = "\u200e";

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const JALALI_MONTHS = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];

function normalizeDate(value: string | null | undefined) {
  if (!value) return null;
  return /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
}

function gregorianToJalali(year: number, month: number, day: number) {
  const gDaysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const jDaysInMonth = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];
  const gy = year - 1600;
  const gm = month - 1;
  const gd = day - 1;
  let gDayNo = 365 * gy + Math.floor((gy + 3) / 4) - Math.floor((gy + 99) / 100) + Math.floor((gy + 399) / 400);
  for (let index = 0; index < gm; index += 1) gDayNo += gDaysInMonth[index];
  if (gm > 1 && (gy + 1600) % 4 === 0 && ((gy + 1600) % 100 !== 0 || (gy + 1600) % 400 === 0)) gDayNo += 1;
  gDayNo += gd;

  let jDayNo = gDayNo - 79;
  const jNp = Math.floor(jDayNo / 12053);
  jDayNo %= 12053;
  let jy = 979 + 33 * jNp + 4 * Math.floor(jDayNo / 1461);
  jDayNo %= 1461;
  if (jDayNo >= 366) {
    jy += Math.floor((jDayNo - 1) / 365);
    jDayNo = (jDayNo - 1) % 365;
  }
  let jm = 0;
  while (jm < 11 && jDayNo >= jDaysInMonth[jm]) {
    jDayNo -= jDaysInMonth[jm];
    jm += 1;
  }
  return { year: jy, month: jm + 1, day: jDayNo + 1 };
}

export function formatTehranDateTime(value: string | null | undefined, includeTime = true) {
  const parts = formatTehranDateParts(value);
  if (!parts) return "نامشخص";
  const dateText = `شمسی: ${parts.jalali} | میلادی: ${parts.gregorian}`;
  if (!includeTime) return dateText;
  return `${dateText} | ساعت: ${parts.time}`;
}

export function formatTehranDateParts(value: string | null | undefined) {
  const normalized = normalizeDate(value);
  if (!normalized) return null;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return null;

  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: TEHRAN_TIME_ZONE,
  }).formatToParts(date);
  const valueOf = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  const day = Number(valueOf("day"));
  const month = Number(valueOf("month"));
  const year = valueOf("year");
  const jalali = gregorianToJalali(Number(year), month, day);
  const jalaliText = `${jalali.day} ${JALALI_MONTHS[jalali.month - 1]} ${jalali.year}`;
  const gregorianText = `${LTR_MARK}${day} ${MONTHS[month - 1] ?? valueOf("month")} ${year}${LTR_MARK}`;
  return {
    jalali: jalaliText,
    gregorian: gregorianText,
    time: `${valueOf("hour")}:${valueOf("minute")}`,
  };
}
