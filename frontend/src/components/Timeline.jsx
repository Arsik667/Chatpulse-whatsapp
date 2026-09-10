import { useState } from "react";
import { Line } from "react-chartjs-2";

import { ACCENT, baseOptions } from "../charts.js";
import { mondayOf } from "../format.js";
import { useI18n } from "../i18n.js";
import { Empty, Section } from "./ui.jsx";

const STEPS = ["day", "week", "month"];

// Бэкенд отдаёт сообщения по дням (с нулями для пустых дней); недели и месяцы
// собираем здесь — на длинных чатах дневной график превращается в шум.
function aggregate(dates, counts, step, f, t) {
  if (step === "day") return { labels: dates.map(f.dateShort), values: counts };
  const buckets = new Map();
  dates.forEach((date, i) => {
    const key = step === "month" ? date.slice(0, 7) : mondayOf(date);
    buckets.set(key, (buckets.get(key) ?? 0) + counts[i]);
  });
  const keys = [...buckets.keys()];
  return {
    labels: keys.map((k) => (step === "month" ? f.month(k) : t.weekFrom(f.dateShort(k)))),
    values: keys.map((k) => buckets.get(k)),
  };
}

const defaultStep = (days) => (days <= 120 ? "day" : days <= 730 ? "week" : "month");

export default function Timeline({ timeline }) {
  const { t, f } = useI18n();
  const [step, setStep] = useState(() => defaultStep(timeline.dates.length));
  const { labels, values } = aggregate(timeline.dates, timeline.counts, step, f, t);
  const peak = timeline.most_active_day;

  const data = {
    labels,
    datasets: [
      {
        data: values,
        borderColor: ACCENT,
        backgroundColor: `${ACCENT}22`,
        fill: true,
        cubicInterpolationMode: "monotone", // сглаживает, но не уводит линию ниже нуля
        pointRadius: values.length > 60 ? 0 : 2,
        borderWidth: 2,
      },
    ],
  };
  const options = {
    ...baseOptions,
    interaction: { mode: "index", intersect: false },
    scales: {
      x: { grid: { display: false }, ticks: { maxTicksLimit: 10, maxRotation: 0, autoSkip: true } },
      y: { beginAtZero: true, ticks: { precision: 0 } },
    },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx) => ` ${t.msgs(f.int(ctx.raw))}` } },
    },
  };

  return (
    <Section title={t.timelineTitle} subtitle={t.timelineSub} className="timeline">
      <div className="segmented" role="group" aria-label={t.stepAria}>
        {STEPS.map((key) => (
          <button
            key={key}
            type="button"
            className={step === key ? "active" : ""}
            aria-pressed={step === key}
            onClick={() => setStep(key)}
          >
            {t.steps[key]}
          </button>
        ))}
      </div>
      {timeline.dates.length > 1 ? (
        <div className="chart tall">
          <Line data={data} options={options} />
        </div>
      ) : (
        <Empty>{t.oneDay(f.date(peak.date))}</Empty>
      )}

      <div className="grid-2 facts">
        <div>
          <h3>{t.peakDay}</h3>
          <p className="big">
            {f.date(peak.date)} <span className="muted">({f.weekdayOf(peak.date)})</span>
          </p>
          <p className="muted">{t.msgs(f.int(peak.count))}</p>
        </div>
        <div>
          <h3>{t.silencesTitle}</h3>
          {timeline.longest_silences.length ? (
            <ol className="silences">
              {timeline.longest_silences.map((s) => (
                <li key={s.start}>
                  <strong>{f.duration(s.duration_s)}</strong>
                  <span className="muted">
                    {" "}
                    {f.dateTime(s.start)} → {f.dateTime(s.end)}, {t.brokenBy(s.broken_by)}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">{t.noPauses}</p>
          )}
        </div>
      </div>
    </Section>
  );
}
