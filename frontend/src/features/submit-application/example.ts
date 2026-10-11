// Пример заявки для подсказок по Tab: каждый раз новый, в форматах мира (см. shared/demo).
import type { Branch } from "@/entities/branch";
import {
  bankAccount,
  card,
  DEMO,
  deviceId,
  helperId,
  intBetween,
  legalInn,
  logNormalFactor,
  phone,
  pick,
  pinfl,
  stepBetween,
} from "@/shared/demo";

import type { Channel, TextKey } from "./form";

type CommonKey = Exclude<
  TextKey,
  "branchId" | "employeeId" | "district" | "registrationMahalla" | "amount" | "termMonths"
>;

export interface Example {
  common: Record<CommonKey, string>;
  loan: Record<Channel, { amount: string; termMonths: string }>;
  /** Филиал и сотрудник примера выбираются из справочника бэка по случайному номеру. */
  branchSeed: number;
  employeeSeed: number;
  mahalla: number;
}

export function makeExample(): Example {
  const item = pick(DEMO.items);
  const [minQuantity, maxQuantity] = item.quantity;
  const unitPrice = Math.round((item.median * logNormalFactor(item.sigma)) / DEMO.priceStep) * DEMO.priceStep;
  const quantity = intBetween(minQuantity, maxQuantity);
  const { amount } = DEMO.online;
  return {
    common: {
      pinfl: pinfl(),
      phone: phone(),
      deviceId: deviceId(),
      address: `ул. ${pick(DEMO.streets)}, ${String(intBetween(1, 120))}`,
      employerInn: legalInn(),
      purpose: pick(DEMO.purposes),
      account: card(),
      helperId: helperId(),
      supplierInn: legalInn(),
      supplierAccount: bankAccount(),
      itemCode: item.code,
      unit: item.unit,
      unitPrice: String(unitPrice),
      quantity: String(quantity),
    },
    loan: {
      online: {
        amount: String(stepBetween(amount.min, amount.max, amount.step)),
        termMonths: String(pick(DEMO.online.termMonths)),
      },
      // Программный займ покрывает договор поставки: сумма — цена за единицу на количество.
      program: { amount: String(unitPrice * quantity), termMonths: String(pick(DEMO.program.termMonths)) },
    },
    branchSeed: intBetween(0, Number.MAX_SAFE_INTEGER),
    employeeSeed: intBetween(0, Number.MAX_SAFE_INTEGER),
    mahalla: intBetween(1, DEMO.helpersPerDistrict),
  };
}

function seeded<T>(items: readonly T[], seed: number): T | undefined {
  return items[seed % Math.max(items.length, 1)];
}

/** Значение примера для поля формы; филиал и район — из справочника филиалов бэка. */
export function exampleValue(
  example: Example,
  key: TextKey,
  channel: Channel,
  branches: readonly Branch[],
  branch: Branch | undefined,
): string {
  switch (key) {
    case "branchId":
      return seeded(branches, example.branchSeed)?.id ?? "";
    case "employeeId":
      return seeded(branch?.employees ?? [], example.employeeSeed)?.id ?? "";
    case "district":
      return (branch ?? seeded(branches, example.branchSeed))?.district ?? "";
    case "registrationMahalla": {
      // Формат мира: «<район>, махалля N» — по району выбранного филиала.
      const district = (branch ?? seeded(branches, example.branchSeed))?.district;
      return district === undefined ? "" : `${district}, махалля ${String(example.mahalla)}`;
    }
    case "amount":
    case "termMonths":
      return example.loan[channel][key];
    default:
      return example.common[key];
  }
}
