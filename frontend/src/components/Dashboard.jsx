import { Bar, Doughnut } from "react-chartjs-2";

import { ACCENT, ACCENT_2, MISSED, PALETTE, REST_COLOR, baseOptions, horizontalOptions } from "../charts.js";
import { useI18n } from "../i18n.js";
import Heatmap from "./Heatmap.jsx";
import Timeline from "./Timeline.jsx";
import { Empty, Kpi, Section } from "./ui.jsx";
import WordCloud from "./WordCloud.jsx";

const GAP_OPTIONS = [1, 3, 6, 12, 24];
const PLATFORMS = { android: "Android", ios: "iOS" };
const MAX_SLICES = 7; // в «пончике» больше кусков не читается — остальных объединяем

// --- шапка и ключевые цифры -----------------------------------------------------------

function Header({ meta, fileName, gapHours, onGapChange, loading }) {
  const { t, f } = useI18n();
  const period = meta.first_message
    ? `${f.date(meta.first_message)} – ${f.date(meta.last_message)} · ${meta.days} ${t.days(meta.days)}`
    : t.noMessages;
  return (
    <div className="dash-header">
      <div>
        <h1>{fileName}</h1>
        <p className="subtitle">
          WhatsApp · {PLATFORMS[meta.platform]} · {period}
          {meta.participants.length > 0 && ` · ${meta.participants.join(", ")}`}
        </p>
      </div>
      <label className="gap-select">
        {t.gapLabel}
        <select value={gapHours} onChange={(e) => onGapChange(Number(e.target.value))} disabled={loading}>
          {GAP_OPTIONS.map((h) => (
            <option key={h} value={h}>
              {t.hours(h)}
            </option>
          ))}
        </select>
        {loading && <span className="spinner small" aria-label={t.recalculating} />}
      </label>
    </div>
  );
}

function Kpis({ summary, calls }) {
  const { t, f } = useI18n();
  return (
    <div className="kpis">
      <Kpi value={f.int(summary.messages)} label={t.kpiMessages(summary.messages)} />
      <Kpi value={f.int(summary.words)} label={t.kpiWords(summary.words)} />
      <Kpi value={f.int(summary.media)} label={t.kpiMedia} />
      <Kpi value={f.int(summary.links)} label={t.kpiLinks(summary.links)} />
      <Kpi value={f.num(summary.avg_words_per_message)} label={t.kpiAvgWords} />
      <Kpi value={f.int(calls.total)} label={t.kpiCalls(calls.total)} />
    </div>
  );
}

// --- участники --------------------------------------------------------------------------

function slices(people, key, othersLabel) {
  const sorted = [...people].sort((a, b) => b[key] - a[key]);
  if (sorted.length <= MAX_SLICES + 1) return sorted.map((p) => ({ name: p.name, value: p[key] }));
  const rest = sorted.slice(MAX_SLICES).reduce((sum, p) => sum + p[key], 0);
  return [...sorted.slice(0, MAX_SLICES).map((p) => ({ name: p.name, value: p[key] })), { name: othersLabel, value: rest }];
}

function ShareDoughnut({ data, colorOf, unit }) {
  const { f } = useI18n();
  const total = data.reduce((sum, d) => sum + d.value, 0) || 1;
  const pct = (value) => f.pct(Math.round((1000 * value) / total) / 10);
  const chart = {
    // проценты прямо в легенде — чтобы не приходилось наводить мышь
    labels: data.map((d) => `${d.name} · ${pct(d.value)}`),
    datasets: [
      {
        data: data.map((d) => d.value),
        backgroundColor: data.map((d) => colorOf(d.name)),
        borderWidth: 0,
      },
    ],
  };
  const options = {
    ...baseOptions,
    cutout: "62%",
    plugins: {
      legend: { position: "right", labels: { boxWidth: 12, padding: 12 } },
      tooltip: { callbacks: { label: (ctx) => ` ${f.int(ctx.raw)} ${unit}` } },
    },
  };
  return (
    <div className="chart">
      <Doughnut data={chart} options={options} />
    </div>
  );
}

function ParticipantsTable({ participants, responseTimes }) {
  const { t, f } = useI18n();
  const replies = Object.fromEntries(responseTimes.map((r) => [r.name, r]));
  const solo = participants.length < 2; // одному участнику «начинать разговор» не с кем
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {t.tableHead.map((title) => (
              <th key={title}>{title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {participants.map((p) => (
            <tr key={p.name}>
              <td>{p.name}</td>
              <td>{f.int(p.messages)}</td>
              <td>{f.pct(p.share)}</td>
              <td>{f.int(p.words)}</td>
              <td>{f.num(p.avg_words)}</td>
              <td>{f.int(p.media)}</td>
              <td>{f.int(p.links)}</td>
              <td>{solo ? "—" : `${f.int(p.initiations)} · ${f.pct(p.initiation_share)}`}</td>
              <td>{f.duration(replies[p.name]?.median_s)}</td>
              <td>{f.duration(replies[p.name]?.mean_s)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResponseTimes({ responseTimes, hasSeconds }) {
  const { t, f } = useI18n();
  if (!responseTimes.length) return <Empty>{t.needTwo}</Empty>;
  const data = {
    labels: responseTimes.map((r) => r.name),
    datasets: [{ data: responseTimes.map((r) => r.median_s / 60), backgroundColor: ACCENT, borderRadius: 4 }],
  };
  const options = {
    ...horizontalOptions,
    scales: {
      ...horizontalOptions.scales,
      x: { beginAtZero: true, title: { display: true, text: t.minutesAxis } },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const r = responseTimes[ctx.dataIndex];
            return [
              ` ${t.median}: ${f.duration(r.median_s)}`,
              ` ${t.mean}: ${f.duration(r.mean_s)}`,
              ` ${t.replies}: ${f.int(r.responses)}`,
            ];
          },
        },
      },
    },
  };
  return (
    <>
      <div className="chart" style={{ height: Math.max(140, 56 * responseTimes.length) }}>
        <Bar data={data} options={options} />
      </div>
      {!hasSeconds && <p className="note">{t.noSecondsNote}</p>}
    </>
  );
}

// --- звонки ------------------------------------------------------------------------------

function Calls({ calls }) {
  const { t, f } = useI18n();
  if (!calls.total) return <Empty>{t.noCalls}</Empty>;
  const people = calls.by_participant;
  const data = {
    labels: people.map((p) => p.name),
    datasets: [
      { label: t.callsAnswered, data: people.map((p) => p.completed), backgroundColor: ACCENT, borderRadius: 4 },
      { label: t.callsMissedLegend, data: people.map((p) => p.missed), backgroundColor: MISSED, borderRadius: 4 },
    ],
  };
  const options = {
    ...horizontalOptions,
    scales: {
      x: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
      y: { stacked: true, grid: { display: false } },
    },
    plugins: {
      legend: { display: true, position: "bottom", labels: { boxWidth: 12 } },
      tooltip: {
        callbacks: { footer: (items) => t.callDuration(f.duration(people[items[0].dataIndex].duration_s)) },
      },
    },
  };
  return (
    <>
      <div className="mini-kpis">
        <Kpi value={f.int(calls.missed)} label={t.callsMissed} />
        <Kpi value={f.duration(calls.total_duration_s)} label={t.callsTotal} />
        <Kpi value={f.duration(calls.avg_duration_s)} label={t.callsAvg} />
        <Kpi value={f.duration(calls.longest_s)} label={t.callsLongest} />
      </div>
      <p className="note">{t.callsNote(f.int(calls.voice), f.int(calls.video))}</p>
      <div className="chart" style={{ height: Math.max(150, 50 * people.length + 40) }}>
        <Bar data={data} options={options} />
      </div>
    </>
  );
}

// --- активность ---------------------------------------------------------------------------

function ActivityBars({ labels, values, color }) {
  const { t, f } = useI18n();
  const data = { labels, datasets: [{ data: values, backgroundColor: color, borderRadius: 3 }] };
  const options = {
    ...baseOptions,
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 6 } },
      y: { beginAtZero: true, ticks: { precision: 0 } },
    },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx) => ` ${t.msgs(f.int(ctx.raw))}` } },
    },
  };
  return (
    <div className="chart">
      <Bar data={data} options={options} />
    </div>
  );
}

// --- эмодзи --------------------------------------------------------------------------------

function EmojiGrid({ emoji }) {
  const { t, f } = useI18n();
  if (!emoji.length) return <Empty>{t.noEmoji}</Empty>;
  const max = emoji[0].count;
  return (
    <div className="emoji-grid">
      {emoji.map((e) => (
        <div className="emoji-card" key={e.emoji} title={`${e.emoji} — ${f.int(e.count)}`}>
          <span className="emoji">{e.emoji}</span>
          <span className="emoji-count">{f.int(e.count)}</span>
          <span className="emoji-bar">
            <i style={{ width: `${(100 * e.count) / max}%` }} />
          </span>
        </div>
      ))}
    </div>
  );
}

// --- дашборд целиком ------------------------------------------------------------------------

export default function Dashboard({ report, fileName, gapHours, onGapChange, loading, error }) {
  const { t, f } = useI18n();
  const { meta, summary, participants, response_times: responseTimes, calls, activity, timeline } = report;

  // Цвет участника одинаковый во всех графиках: по порядку в списке (по числу сообщений).
  const colorIndex = Object.fromEntries(meta.participants.map((name, i) => [name, i]));
  const colorOf = (name) => (name in colorIndex ? PALETTE[colorIndex[name] % PALETTE.length] : REST_COLOR);

  return (
    <div className={`dashboard${loading ? " is-loading" : ""}`}>
      <Header meta={meta} fileName={fileName} gapHours={gapHours} onGapChange={onGapChange} loading={loading} />

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {report.warnings.length > 0 && (
        <ul className="warnings">
          {report.warnings.map((code) => (
            <li key={code}>{t.warnings[code] ?? code}</li>
          ))}
        </ul>
      )}

      <Kpis summary={summary} calls={calls} />

      {summary.messages === 0 ? (
        <Section title={t.nothingTitle}>
          <Empty>{t.nothingText}</Empty>
        </Section>
      ) : (
        <>
          <div className="grid-2">
            <Section title={t.whoWritesTitle} subtitle={t.whoWritesSub}>
              <ShareDoughnut data={slices(participants, "messages", t.others)} colorOf={colorOf} unit={t.unitMessages} />
            </Section>
            <Section title={t.whoStartsTitle} subtitle={t.whoStartsSub(gapHours)}>
              {participants.length > 1 ? (
                <ShareDoughnut data={slices(participants, "initiations", t.others)} colorOf={colorOf} unit={t.unitTimes} />
              ) : (
                <Empty>{t.needTwo}</Empty>
              )}
            </Section>
          </div>

          <Section title={t.participantsTitle}>
            <ParticipantsTable participants={participants} responseTimes={responseTimes} />
          </Section>

          <div className="grid-2">
            <Section title={t.replyTitle} subtitle={t.replySub(gapHours)}>
              <ResponseTimes responseTimes={responseTimes} hasSeconds={meta.has_seconds} />
            </Section>
            <Section title={t.callsTitle}>
              <Calls calls={calls} />
            </Section>
          </div>

          <Section title={t.heatmapTitle} subtitle={t.heatmapSub}>
            <Heatmap matrix={activity.matrix} />
          </Section>

          <div className="grid-2">
            <Section title={t.byHourTitle}>
              <ActivityBars
                labels={activity.by_hour.map((_, h) => String(h).padStart(2, "0"))}
                values={activity.by_hour}
                color={ACCENT}
              />
            </Section>
            <Section title={t.byWeekdayTitle}>
              <ActivityBars labels={f.weekdays} values={activity.by_weekday} color={ACCENT_2} />
            </Section>
          </div>

          <Timeline timeline={timeline} />

          <div className="grid-2">
            <Section title={t.wordsTitle} subtitle={t.wordsSub}>
              <WordCloud words={report.top_words} />
            </Section>
            <Section title={t.emojiTitle}>
              <EmojiGrid emoji={report.top_emoji} />
            </Section>
          </div>
        </>
      )}
    </div>
  );
}
