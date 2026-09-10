import { useI18n } from "../i18n.js";
import { Empty } from "./ui.jsx";

// Простой хеш строки: слова перемешиваются, но всегда одинаково — облако не «прыгает».
function hash(word) {
  let h = 0;
  for (const ch of word) h = (h * 31 + ch.codePointAt(0)) | 0;
  return h;
}

// Облако без библиотек: размер шрифта растёт с частотой слова. Корень сглаживает
// разницу, иначе самое частое слово было бы огромным, а остальные — мелкими.
export default function WordCloud({ words }) {
  const { t, f } = useI18n();
  if (!words.length) return <Empty>{t.noWords}</Empty>;

  const max = words[0].count;
  const min = words[words.length - 1].count;
  const weight = (count) => (max === min ? 1 : Math.sqrt((count - min) / (max - min)));
  const shuffled = [...words].sort((a, b) => hash(a.word) - hash(b.word));

  return (
    <div className="cloud">
      {shuffled.map(({ word, count }) => {
        const w = weight(count);
        return (
          <span
            key={word}
            title={`${word}: ${f.int(count)}`}
            className={w > 0.6 ? "hot" : ""}
            style={{ fontSize: `${0.8 + w * 1.8}rem`, opacity: 0.55 + w * 0.45 }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
}
