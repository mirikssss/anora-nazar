// Пример перевода для подсказок по Tab: карта в форматах мира и доля суммы кредита (см. shared/demo).
import { card, DEMO } from "@/shared/demo";

export interface TransferExample {
  card: string;
  /** Доля суммы кредита: сама сумма зависит от выбранной заявки. */
  share: number;
}

export function makeExample(): TransferExample {
  const [min, max] = DEMO.transferCreditShare;
  return { card: card(), share: min + Math.random() * (max - min) };
}

export function exampleAmount(example: TransferExample, loanAmount: number | null): string {
  if (loanAmount === null) return "";
  return String(Math.round((loanAmount * example.share) / DEMO.priceStep) * DEMO.priceStep);
}
