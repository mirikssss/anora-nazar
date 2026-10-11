// Форматы идентификаторов — как в генераторе мира (backend/src/world/identifiers.py), чтобы подсказка
// проходила проверки бэка и давала осмысленные признаки (пол и возраст из ПИНФЛ).
import { digits, hex, intBetween, pick } from "./random";
import { DEMO } from "./values";

const PINFL_CHECK_WEIGHTS = [7, 3, 1] as const;
const MS_PER_DAY = 86_400_000;
const DAYS_PER_YEAR = 365.25;

function pad(value: number, width: number): string {
  return String(value).padStart(width, "0");
}

function checkDigit(body: string): string {
  let total = 0;
  for (let index = 0; index < body.length; index += 1) {
    total += Number(body.charAt(index)) * (PINFL_CHECK_WEIGHTS[index % PINFL_CHECK_WEIGHTS.length] ?? 0);
  }
  return String(total % 10);
}

/** ПИНФЛ: цифра века и пола, дата рождения ДДММГГ, код района, номер, контрольная цифра. */
export function pinfl(): string {
  const [minAge, maxAge] = DEMO.applicantAgeYears;
  const ageDays = intBetween(Math.round(minAge * DAYS_PER_YEAR), Math.round(maxAge * DAYS_PER_YEAR));
  const born = new Date(Date.now() - ageDays * MS_PER_DAY);
  const male = Math.random() < 0.5;
  const century = born.getUTCFullYear() < 2000 ? (male ? "3" : "4") : male ? "5" : "6";
  const body = [
    century,
    pad(born.getUTCDate(), 2),
    pad(born.getUTCMonth() + 1, 2),
    pad(born.getUTCFullYear() % 100, 2),
    pad(intBetween(1, 999), 3),
    digits(3),
  ].join("");
  return body + checkDigit(body);
}

export function phone(): string {
  return `998${pick(DEMO.phoneOperatorCodes)}${digits(7)}`;
}

export function deviceId(): string {
  return `dev-${hex(16)}`;
}

/** ИНН юрлица: 9 цифр, начинается с 2 или 3. */
export function legalInn(): string {
  return `${pick(["2", "3"])}${digits(8)}`;
}

/** Счёт в банке Узбекистана — 20 цифр. */
export function bankAccount(): string {
  return `${pick(["2", "1"])}${digits(19)}`;
}

/** Карта для зачисления онлайн-микрозайма. */
export function card(): string {
  return `${pick(DEMO.cardPrefixes)}${digits(12)}`;
}

/** Код помощника хокима — как в мире: HLP-район-номер. */
export function helperId(): string {
  return `HLP-${pad(intBetween(1, DEMO.helperDistricts), 3)}-${pad(intBetween(1, DEMO.helpersPerDistrict), 2)}`;
}
