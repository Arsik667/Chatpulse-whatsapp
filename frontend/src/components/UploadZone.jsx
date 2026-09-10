import { useEffect, useRef, useState } from "react";

// Синтетические чаты из examples/ — Vite кладёт их в сборку отдельными файлами.
import demoEnUrl from "../../../examples/demo_chat_en.txt?url";
import demoRuUrl from "../../../examples/demo_chat.txt?url";
import { useI18n } from "../i18n.js";

const EXTENSIONS = [".txt", ".zip"];
const DEMO = {
  ru: { url: demoRuUrl, name: "demo_chat.txt" },
  en: { url: demoEnUrl, name: "demo_chat_en.txt" },
};

export default function UploadZone({ onFile, loading, error, maxMb, backendDown }) {
  const { lang, t } = useI18n();
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  // храним ключ ошибки, а не текст — чтобы при смене языка она тоже переводилась
  const [localError, setLocalError] = useState("");

  // Проверяем то, что можно проверить без сервера: расширение и размер.
  function pick(file) {
    if (!file || loading) return;
    if (!EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext))) {
      setLocalError("errExtension");
      return;
    }
    if (file.size > maxMb * 1024 * 1024) {
      setLocalError("errTooLarge");
      return;
    }
    setLocalError("");
    onFile(file);
  }

  // Демо проходит тот же путь, что и настоящий файл: File → POST /api/analyze.
  async function pickDemo() {
    const demo = DEMO[lang];
    try {
      const blob = await (await fetch(demo.url)).blob();
      pick(new File([blob], demo.name, { type: "text/plain" }));
    } catch {
      setLocalError("errDemo");
    }
  }

  // Ссылка вида /?demo сразу открывает демо. Параметр убираем из адреса,
  // иначе «Загрузить другой чат» снова открывал бы демо.
  const demoStarted = useRef(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (demoStarted.current || !params.has("demo")) return;
    demoStarted.current = true; // StrictMode в dev вызывает эффект дважды
    params.delete("demo");
    const query = params.toString();
    window.history.replaceState(null, "", window.location.pathname + (query ? `?${query}` : ""));
    pickDemo();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };
  // dragleave срабатывает и при переходе на дочерний элемент — такие события пропускаем
  const onDragLeave = (e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false);
  };
  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files[0]);
  };

  const message = (localError && (localError === "errTooLarge" ? t.errTooLarge(maxMb) : t[localError])) || error;

  return (
    <section className="upload">
      <h1>{t.heroTitle}</h1>
      <p className="lead">{t.heroLead}</p>

      <div
        className={`dropzone${dragging ? " dragging" : ""}${loading ? " busy" : ""}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {loading ? (
          <>
            <div className="spinner" aria-hidden="true" />
            <p>{t.analyzing}</p>
          </>
        ) : (
          <>
            <div className="dropzone-icon" aria-hidden="true">📂</div>
            <p>
              <strong>{t.dropHere}</strong> {t.or}
            </p>
            <button type="button" className="primary" onClick={() => input.current.click()}>
              {t.chooseFile}
            </button>
            <p className="hint">{t.fileHint(maxMb)}</p>
          </>
        )}
        <input
          ref={input}
          type="file"
          accept=".txt,.zip"
          hidden
          onChange={(e) => {
            pick(e.target.files[0]);
            e.target.value = ""; // чтобы можно было выбрать тот же файл ещё раз
          }}
        />
      </div>

      <p className="demo">
        {t.demoPrefix}{" "}
        <button type="button" className="link" onClick={pickDemo} disabled={loading}>
          {t.demoLink}
        </button>{" "}
        {t.demoSuffix}
      </p>

      {message && (
        <p className="error" role="alert">
          {message}
        </p>
      )}
      {backendDown && !message && (
        <p className="error" role="alert">
          {t.backendDown}
        </p>
      )}

      <details className="howto">
        <summary>{t.howtoTitle}</summary>
        <ul>
          <li>
            <strong>Android:</strong> {t.howtoAndroid}
          </li>
          <li>
            <strong>iPhone:</strong> {t.howtoIphone}
          </li>
          <li>{t.howtoSave}</li>
        </ul>
      </details>
    </section>
  );
}
