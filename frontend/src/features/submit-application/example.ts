// Пример заявки для подсказок по Tab: каждый раз новый, в форматах мира (см. shared/demo). Филиал,
// помощник хокима и поставщик берутся из справочников бэка по случайному номеру примера.
import type { Branch } from "@/entities/branch";
import type { Helper, Supplier } from "@/entities/program";
import {
  card,
  DEMO,
  deviceId,
  intBetween,
  legalInn,
  logNormalFactor,
  phone,
  pick,
  pinfl,
  stepBetween,
} from "@/shared/demo";

import type { Channel, TextKey } from "./form";

type DirectoryKey =
  | "branchId"
  | "employeeId"
  | "district"
  | "registrationMahalla"
  | "helperId"
  | "helperMahalla"
  | "supplierInn"
  | "supplierAccount"
  | "amount"
  | "termMonths";
type CommonKey = Exclude<TextKey, DirectoryKey>;

export interface Example {
  common: Record<CommonKey, string>;
  loan: Record<Channel, { amount: string; termMonths: string }>;
  /** Категория товара примера: по ней фильтруются поставщики. */
  category: string;
  seed: number;
  mahalla: number;
}

/** Справочники бэка, из которых пример берёт филиал, помощника и поставщика. */
export interface ExampleContext {
  channel: Channel;
  branches: readonly Branch[];
  branch: Branch | undefined;
  /** Помощники и поставщики района доставки. */
  helpers: readonly Helper[];
  suppliers: readonly Supplier[];
  /** Районы, где на платформе программ есть и помощники, и поставщики. */
  programDistricts: ReadonlySet<string>;
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
    category: item.category,
    seed: intBetween(0, Number.MAX_SAFE_INTEGER),
    mahalla: intBetween(1, DEMO.helpersPerDistrict),
  };
}

function seeded<T>(items: readonly T[], seed: number): T | undefined {
  return items[seed % Math.max(items.length, 1)];
}

/** Филиал примера: выбранный проверяющим, иначе — случайный из справочника. Для программного займа —
 *  только филиал района, где есть помощники и поставщики: иначе заявку не собрать из справочников. */
export function exampleBranch(example: Example, context: ExampleContext): Branch | undefined {
  if (context.branch !== undefined) return context.branch;
  const candidates =
    context.channel === "program"
      ? context.branches.filter((branch) => context.programDistricts.has(branch.district))
      : context.branches;
  // Пока справочники программ не пришли, кандидатов нет — берём любой филиал, а не оставляем пустым.
  return seeded(candidates.length > 0 ? candidates : context.branches, example.seed);
}

export function exampleHelper(example: Example, helpers: readonly Helper[]): Helper | undefined {
  return seeded(helpers, example.seed);
}

export function exampleSupplier(example: Example, suppliers: readonly Supplier[]): Supplier | undefined {
  return seeded(suppliers, example.seed);
}

export function helperMahalla(helper: Helper): string {
  return `${helper.district}, ${helper.mahalla}`;
}

/** Значение примера для поля формы; «» — справочник ещё не загружен или пуст. */
export function exampleValue(example: Example, key: TextKey, context: ExampleContext): string {
  const branch = exampleBranch(example, context);
  const helper = exampleHelper(example, context.helpers);
  const supplier = exampleSupplier(example, context.suppliers);
  switch (key) {
    case "branchId":
      return branch?.id ?? "";
    case "employeeId":
      return seeded(branch?.employees ?? [], example.seed)?.id ?? "";
    case "district":
      return branch?.district ?? "";
    case "registrationMahalla":
      // Честный пример: в программе заявитель из махалли своего помощника (иначе — сигнал зоны 3).
      // Формат мира: «<район>, махалля N».
      if (context.channel === "program" && helper !== undefined) return helperMahalla(helper);
      return branch === undefined ? "" : `${branch.district}, махалля ${String(example.mahalla)}`;
    case "helperId":
      return helper?.id ?? "";
    case "helperMahalla":
      return helper === undefined ? "" : helperMahalla(helper);
    case "supplierInn":
      return supplier?.inn ?? "";
    case "supplierAccount":
      return supplier?.account ?? "";
    case "amount":
    case "termMonths":
      return example.loan[context.channel][key];
    default:
      return example.common[key];
  }
}

/** Категория товара для фильтра поставщиков: по коду товара из формы, иначе — товара примера. */
export function itemCategory(itemCode: string, example: Example): string {
  return DEMO.items.find((item) => item.code === itemCode.trim())?.category ?? example.category;
}
