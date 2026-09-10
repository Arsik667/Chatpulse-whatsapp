// Тексты интерфейса на русском и английском. Компоненты берут их через
// useI18n(): t — словарь текущего языка, f — форматирование чисел и дат.
// Тексты ошибок бэкенд присылает сам на нужном языке (?lang=), а предупреждения
// в отчёте — кодами, их переводит словарь ниже (t.warnings).
import { createContext, useContext } from "react";

import { makeFormat } from "./format.js";

export const LANGS = ["ru", "en"];
const STORAGE_KEY = "chatpulse-lang";

/** 1 сообщение · 2 сообщения · 5 сообщений */
function pluralRu(n, one, few, many) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

const pluralEn = (n, one, many) => (n === 1 ? one : many);

const ru = {
  pageTitle: "ChatPulse — анализ чатов WhatsApp",
  switchLang: "EN",
  switchLangTitle: "Switch to English",
  newChat: "Загрузить другой чат",
  footer: "🔒 Файл анализируется в памяти локального бэкенда и нигде не сохраняется. Сторонних запросов страница не делает.",
  errNetwork: (url) => `Не удалось связаться с бэкендом (${url}). Он запущен?`,
  errServer: (status) => `Ошибка сервера (${status})`,

  // экран загрузки
  heroTitle: "Что происходит в вашем чате?",
  heroLead:
    "Загрузите экспорт WhatsApp — ChatPulse посчитает, кто пишет больше, кто первым начинает разговор, как быстро вы отвечаете и в какие часы чат оживает.",
  analyzing: "Считаем статистику…",
  dropHere: "Перетащите файл сюда",
  or: "или",
  chooseFile: "Выбрать файл",
  fileHint: (mb) => `.txt или .zip (экспорт с медиа) · до ${mb} МБ`,
  demoPrefix: "Нет под рукой экспорта?",
  demoLink: "Попробуйте на демо-чате",
  demoSuffix: "— переписка выдуманная.",
  errExtension: "Нужен экспорт WhatsApp: файл .txt или .zip.",
  errTooLarge: (mb) => `Файл больше ${mb} МБ. Экспортируйте чат без медиа — это один .txt.`,
  errDemo: "Не удалось загрузить демо-чат.",
  backendDown: "Бэкенд не отвечает. Запустите его — команды есть в README.",
  howtoTitle: "Как экспортировать чат из WhatsApp",
  howtoAndroid: "откройте чат → ⋮ → Ещё → Экспорт чата → Без медиафайлов.",
  howtoIphone: "откройте чат → нажмите на имя контакта или группы → Экспорт чата → Без медиафайлов.",
  howtoSave: "Сохраните файл на компьютер и перетащите сюда — .zip распаковывать не нужно.",

  // шапка дашборда и ключевые цифры
  days: (n) => pluralRu(n, "день", "дня", "дней"),
  noMessages: "нет сообщений",
  gapLabel: "Новый разговор после паузы",
  hours: (h) => `${h} ч`,
  recalculating: "Пересчитываем",
  kpiMessages: (n) => pluralRu(n, "сообщение", "сообщения", "сообщений"),
  kpiWords: (n) => pluralRu(n, "слово", "слова", "слов"),
  kpiMedia: "медиа",
  kpiLinks: (n) => pluralRu(n, "ссылка", "ссылки", "ссылок"),
  kpiAvgWords: "слов в сообщении",
  kpiCalls: (n) => pluralRu(n, "звонок", "звонка", "звонков"),
  warnings: {
    no_messages: "В чате нет сообщений от участников — только служебные уведомления.",
    single_participant: "В чате один участник: время ответа и инициатива разговоров не считаются.",
    no_seconds: "В экспорте время без секунд (так пишет Android) — время ответа точно до минуты.",
  },

  // секции
  nothingTitle: "Пока нечего показывать",
  nothingText: "Загрузите другой экспорт — например, чат, где уже есть переписка.",
  whoWritesTitle: "Кто пишет больше",
  whoWritesSub: "Доля сообщений",
  whoStartsTitle: "Кто начинает разговор",
  whoStartsSub: (h) => `Первое сообщение после паузы больше ${h} ч`,
  needTwo: "Нужно хотя бы два участника.",
  others: "Остальные",
  unitMessages: "сообщ.",
  unitTimes: "раз",
  participantsTitle: "Участники",
  tableHead: [
    "Участник", "Сообщений", "Доля", "Слов", "Слов в сообщ.", "Медиа", "Ссылок",
    "Начинал разговор", "Ответ: медиана", "Ответ: среднее",
  ],
  replyTitle: "Время ответа",
  replySub: (h) => `Медиана паузы перед ответом собеседнику; ответы позже ${h} ч не считаются`,
  minutesAxis: "минуты",
  median: "медиана",
  mean: "среднее",
  replies: "ответов",
  noSecondsNote: "Время в экспорте без секунд — точность до минуты.",
  callsTitle: "Звонки",
  noCalls: "Звонков в экспорте нет.",
  callsMissed: "пропущено",
  callsTotal: "всего на связи",
  callsAvg: "в среднем",
  callsLongest: "самый долгий",
  callsNote: (voice, video) => `Голосовых ${voice}, видео ${video}. По участникам — кто звонил.`,
  callsAnswered: "состоялись",
  callsMissedLegend: "пропущены",
  callDuration: (d) => `Длительность: ${d}`,
  heatmapTitle: "Когда вы переписываетесь",
  heatmapSub: "Сообщения по дням недели и часам",
  heatmapAria: "Тепловая карта сообщений по дням недели и часам",
  heatmapCell: (day, from, to, n) => `${day}, ${from}–${to} — ${n} сообщ.`,
  less: "меньше",
  more: "больше",
  byHourTitle: "По часам суток",
  byWeekdayTitle: "По дням недели",
  msgs: (n) => `${n} сообщ.`,
  timelineTitle: "Таймлайн",
  timelineSub: "Сообщения по времени",
  steps: { day: "дни", week: "недели", month: "месяцы" },
  stepAria: "Шаг графика",
  weekFrom: (d) => `с ${d}`,
  oneDay: (d) => `Вся переписка уместилась в один день — ${d}.`,
  peakDay: "Самый активный день",
  silencesTitle: "Самые долгие тишины",
  brokenBy: (who) => `первым написал(а) ${who}`,
  noPauses: "Пауз между сообщениями нет.",
  wordsTitle: "Топ-слова",
  wordsSub: "Без стоп-слов и имён участников; наведите на слово, чтобы увидеть число",
  noWords: "Текстовых сообщений нет.",
  emojiTitle: "Топ-эмодзи",
  noEmoji: "Эмодзи не найдены.",
};

const en = {
  pageTitle: "ChatPulse — WhatsApp chat analytics",
  switchLang: "RU",
  switchLangTitle: "Переключить на русский",
  newChat: "Upload another chat",
  footer: "🔒 The file is analyzed in the local backend's memory and is never stored. The page makes no third-party requests.",
  errNetwork: (url) => `Could not reach the backend (${url}). Is it running?`,
  errServer: (status) => `Server error (${status})`,

  heroTitle: "What's going on in your chat?",
  heroLead:
    "Upload a WhatsApp export — ChatPulse will show who writes more, who starts conversations, how fast you reply and when the chat comes alive.",
  analyzing: "Crunching the numbers…",
  dropHere: "Drop the file here",
  or: "or",
  chooseFile: "Choose a file",
  fileHint: (mb) => `.txt or .zip (export with media) · up to ${mb} MB`,
  demoPrefix: "No export at hand?",
  demoLink: "Try the demo chat",
  demoSuffix: "— the conversation is made up.",
  errExtension: "A WhatsApp export is needed: a .txt or .zip file.",
  errTooLarge: (mb) => `The file is larger than ${mb} MB. Export the chat without media — that's a single .txt.`,
  errDemo: "Could not load the demo chat.",
  backendDown: "The backend isn't responding. Start it — the commands are in the README.",
  howtoTitle: "How to export a chat from WhatsApp",
  howtoAndroid: "open the chat → ⋮ → More → Export chat → Without media.",
  howtoIphone: "open the chat → tap the contact or group name → Export Chat → Without Media.",
  howtoSave: "Save the file to your computer and drop it here — no need to unzip.",

  days: (n) => pluralEn(n, "day", "days"),
  noMessages: "no messages",
  gapLabel: "New conversation after a pause of",
  hours: (h) => `${h} h`,
  recalculating: "Recalculating",
  kpiMessages: (n) => pluralEn(n, "message", "messages"),
  kpiWords: (n) => pluralEn(n, "word", "words"),
  kpiMedia: "media",
  kpiLinks: (n) => pluralEn(n, "link", "links"),
  kpiAvgWords: "words per message",
  kpiCalls: (n) => pluralEn(n, "call", "calls"),
  warnings: {
    no_messages: "The chat has no messages from participants — only system notifications.",
    single_participant: "The chat has a single participant: response times and conversation starts are not computed.",
    no_seconds: "Timestamps in the export have no seconds (Android writes them this way), so response times are accurate to a minute.",
  },

  nothingTitle: "Nothing to show yet",
  nothingText: "Upload another export — for example, a chat that already has messages.",
  whoWritesTitle: "Who writes more",
  whoWritesSub: "Share of messages",
  whoStartsTitle: "Who starts conversations",
  whoStartsSub: (h) => `First message after a pause longer than ${h} h`,
  needTwo: "At least two participants are needed.",
  others: "Others",
  unitMessages: "msgs",
  unitTimes: "times",
  participantsTitle: "Participants",
  tableHead: [
    "Participant", "Messages", "Share", "Words", "Words per msg", "Media", "Links",
    "Started conversations", "Reply: median", "Reply: mean",
  ],
  replyTitle: "Response time",
  replySub: (h) => `Median pause before replying to someone else; replies after ${h} h are not counted`,
  minutesAxis: "minutes",
  median: "median",
  mean: "mean",
  replies: "replies",
  noSecondsNote: "The export has no seconds — accurate to a minute.",
  callsTitle: "Calls",
  noCalls: "No calls in the export.",
  callsMissed: "missed",
  callsTotal: "total call time",
  callsAvg: "on average",
  callsLongest: "longest",
  callsNote: (voice, video) => `${voice} voice, ${video} video. Per participant — who called.`,
  callsAnswered: "answered",
  callsMissedLegend: "missed",
  callDuration: (d) => `Duration: ${d}`,
  heatmapTitle: "When you chat",
  heatmapSub: "Messages by weekday and hour",
  heatmapAria: "Heatmap of messages by weekday and hour",
  heatmapCell: (day, from, to, n) => `${day}, ${from}–${to} — ${n} msgs`,
  less: "less",
  more: "more",
  byHourTitle: "By hour of day",
  byWeekdayTitle: "By weekday",
  msgs: (n) => `${n} msgs`,
  timelineTitle: "Timeline",
  timelineSub: "Messages over time",
  steps: { day: "days", week: "weeks", month: "months" },
  stepAria: "Chart step",
  weekFrom: (d) => `from ${d}`,
  oneDay: (d) => `The whole conversation fits into one day — ${d}.`,
  peakDay: "Most active day",
  silencesTitle: "Longest silences",
  brokenBy: (who) => `broken by ${who}`,
  noPauses: "No pauses between messages.",
  wordsTitle: "Top words",
  wordsSub: "Without stop words and participants' names; hover a word to see its count",
  noWords: "No text messages.",
  emojiTitle: "Top emoji",
  noEmoji: "No emoji found.",
};

export const DICT = { ru, en };

export const I18nContext = createContext(null);
export const useI18n = () => useContext(I18nContext);

export function makeI18n(lang) {
  return { lang, t: DICT[lang], f: makeFormat(lang) };
}

/** Язык при открытии: ?lang= в адресе → сохранённый выбор → русский. */
export function initialLang() {
  const fromUrl = new URLSearchParams(window.location.search).get("lang");
  if (LANGS.includes(fromUrl)) return fromUrl;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (LANGS.includes(saved)) return saved;
  } catch {
    // localStorage бывает недоступен (приватный режим) — просто не помним выбор
  }
  return "ru";
}

export function saveLang(lang) {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // см. initialLang
  }
}
