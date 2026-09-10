import { useCallback, useEffect, useMemo, useState } from "react";

import { API_URL, analyzeChat, fetchHealth } from "./api.js";
import { applyChartLocale, applyChartTheme } from "./charts.js";
import Dashboard from "./components/Dashboard.jsx";
import UploadZone from "./components/UploadZone.jsx";
import { I18nContext, initialLang, makeI18n, saveLang } from "./i18n.js";

const DEFAULT_GAP_HOURS = 6;

// Текст ошибки на текущем языке: сетевые ошибки переводим сами, остальные
// бэкенд уже прислал на нужном языке (?lang=).
function errorText(error, t) {
  if (!error) return "";
  if (error.code === "network") return t.errNetwork(API_URL);
  if (error.code === "server") return t.errServer(error.status);
  return error.message;
}

export default function App() {
  const [lang, setLang] = useState(() => {
    const initial = initialLang();
    applyChartLocale(initial); // до того, как появится первый график
    return initial;
  });
  const i18n = useMemo(() => makeI18n(lang), [lang]);
  const { t } = i18n;

  // Файл держим только в памяти вкладки — чтобы пересчитать отчёт с другой паузой.
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [gapHours, setGapHours] = useState(DEFAULT_GAP_HOURS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null); // null — ещё не знаем, false — бэкенд не отвечает
  const [themeVersion, setThemeVersion] = useState(0);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(false));
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = t.pageTitle;
  }, [lang, t]);

  // Графики Chart.js не видят CSS-переменные сами: при смене системной темы
  // обновляем их цвета и перерисовываем дашборд.
  useEffect(() => {
    applyChartTheme();
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      applyChartTheme();
      setThemeVersion((v) => v + 1);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const switchLang = () => {
    const next = lang === "ru" ? "en" : "ru";
    applyChartLocale(next);
    saveLang(next);
    setLang(next);
  };

  const analyze = useCallback(
    async (nextFile, nextGap) => {
      setLoading(true);
      setError(null);
      try {
        const data = await analyzeChat(nextFile, { gapHours: nextGap, lang });
        setFile(nextFile);
        setGapHours(nextGap);
        setReport(data);
        setHealth((h) => h || { status: "ok" });
      } catch (e) {
        setError(e);
      } finally {
        setLoading(false);
      }
    },
    [lang],
  );

  const reset = () => {
    setFile(null);
    setReport(null);
    setError(null);
  };

  return (
    <I18nContext.Provider value={i18n}>
      <div className="app">
        <header className="topbar">
          <button type="button" className="brand" onClick={reset}>
            <span aria-hidden="true">💬</span> ChatPulse
          </button>
          <div className="topbar-actions">
            <button type="button" className="ghost lang" onClick={switchLang} title={t.switchLangTitle}>
              {t.switchLang}
            </button>
            {report && (
              <button type="button" className="ghost" onClick={reset}>
                {t.newChat}
              </button>
            )}
          </div>
        </header>

        <main className="wrap">
          {report ? (
            <Dashboard
              // при смене темы или языка пересоздаём графики с новыми цветами и подписями
              key={`${themeVersion}-${lang}`}
              report={report}
              fileName={file.name}
              gapHours={gapHours}
              onGapChange={(gap) => analyze(file, gap)}
              loading={loading}
              error={errorText(error, t)}
            />
          ) : (
            <UploadZone
              onFile={(f) => analyze(f, gapHours)}
              loading={loading}
              error={errorText(error, t)}
              maxMb={health?.max_upload_mb ?? 200}
              backendDown={health === false}
            />
          )}
        </main>

        <footer className="footer">{t.footer}</footer>
      </div>
    </I18nContext.Provider>
  );
}
