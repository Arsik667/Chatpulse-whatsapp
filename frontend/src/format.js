// Форматирование чисел, дат и длительностей для выбранного языка —
// те же правила, что в report_cli.py.

const WEEKDAYS = {
  ru: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
  en: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
};
const MONTHS = {
  ru: ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
};
const UNITS = { ru: ["с", "мин", "ч", "дн"], en: ["s", "min", "h", "d"] };

// Даты из API — ISO-строки без часового пояса («время как в чате»).
// Режем строку, а не парсим через new Date(): «2025-09-01» браузер считает
// полночью по UTC и в западных поясах показал бы 31 августа.
const dateParts = (iso) => iso.slice(0, 10).split("-");

/** Понедельник недели, в которую попадает дата (ISO → ISO). От языка не зависит. */
export function mondayOf(iso) {
  const [y, m, d] = dateParts(iso).map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return date.toISOString().slice(0, 10);
}

export function makeFormat(lang) {
  // 12 345 · 2,56 по-русски и 12,345 · 2.56 по-английски
  const numberFormat = new Intl.NumberFormat(lang === "ru" ? "ru-RU" : "en-US", { maximumFractionDigits: 2 });
  const num = (n) => numberFormat.format(n);
  const [sec, min, hr, day] = UNITS[lang];
  const months = MONTHS[lang];
  const weekdays = WEEKDAYS[lang];

  /** 45 с · 3 мин · 1 ч 5 мин · 2 дн 3 ч */
  function duration(seconds) {
    if (seconds === null || seconds === undefined) return "—";
    let s = Math.round(seconds);
    if (s < 60) return `${s} ${sec}`;
    let m = Math.floor(s / 60);
    s %= 60;
    if (m < 60) return `${m} ${min}${s && m < 10 ? ` ${s} ${sec}` : ""}`;
    let h = Math.floor(m / 60);
    m %= 60;
    if (h < 24) return `${h} ${hr}${m ? ` ${m} ${min}` : ""}`;
    const d = Math.floor(h / 24);
    h %= 24;
    return `${d} ${day}${h ? ` ${h} ${hr}` : ""}`;
  }

  /** 01.09.2025 по-русски, 1 Sep 2025 по-английски */
  function date(iso) {
    const [y, m, d] = dateParts(iso);
    return lang === "ru" ? `${d}.${m}.${y}` : `${Number(d)} ${months[m - 1]} ${y}`;
  }

  function dateShort(iso) {
    const [y, m, d] = dateParts(iso);
    return lang === "ru" ? `${d}.${m}.${y.slice(2)}` : `${Number(d)} ${months[m - 1]} ${y.slice(2)}`;
  }

  return {
    num,
    int: num,
    pct: (n) => `${num(n)}%`,
    duration,
    date,
    dateShort,
    dateTime: (iso) => `${date(iso)} ${iso.slice(11, 16)}`,
    month: (yearMonth) => {
      const [y, m] = yearMonth.split("-");
      return `${months[m - 1]} ${y}`;
    },
    weekdays,
    weekdayOf: (iso) => {
      const [y, m, d] = dateParts(iso).map(Number);
      return weekdays[(new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7];
    },
  };
}
