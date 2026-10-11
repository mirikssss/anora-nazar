// Пример акта для подсказок по Tab: код подписанта вне справочника, сегодняшняя дата по поясу банка.
import { env } from "@/shared/config/env";
import { DEMO, intBetween } from "@/shared/demo";

type OtherSigner = keyof typeof DEMO.actSignerPrefixes;

const SIGNER_NUMBER_MAX = 9999;
// en-CA даёт ГГГГ-ММ-ДД — формат поля даты; пояс — банка, а не устройства.
const isoDate = new Intl.DateTimeFormat("en-CA", { timeZone: env.timeZone });

export function signerExample(role: OtherSigner): string {
  return `${DEMO.actSignerPrefixes[role]}-${String(intBetween(1, SIGNER_NUMBER_MAX)).padStart(4, "0")}`;
}

export function todayExample(): string {
  return isoDate.format(new Date());
}

export function isOtherSigner(role: string): role is OtherSigner {
  return role in DEMO.actSignerPrefixes;
}
