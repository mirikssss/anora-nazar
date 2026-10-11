// Знак продукта: «Anora Nazar» жирным, «Anora» красным, без иконки — указание владельца,
// исключение из правила «цвет только для состояний» (CLAUDE.md, «Интерфейс», п. 5).
import { ru } from "@/shared/i18n/ru";

import styles from "./Wordmark.module.css";

export function Wordmark() {
  return (
    <span className={styles.wordmark} aria-label={ru.product.name}>
      <span className={styles.accent} aria-hidden>
        {ru.product.accent}
      </span>{" "}
      <span aria-hidden>{ru.product.rest}</span>
    </span>
  );
}
