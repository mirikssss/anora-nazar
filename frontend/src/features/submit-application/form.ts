// Состояние формы своей заявки и сборка черновика для конвейера. Проверку значений делает бэк;
// здесь — только «поле пустое» и «не число», чтобы не гонять запрос впустую.
import type { ApplicationDraft } from "@/entities/application";
import { ru } from "@/shared/i18n/ru";
import { parseInteger } from "@/shared/lib/format";

import type { SelfBanStatus, SessionEventType } from "./api";

export type Channel = ApplicationDraft["channel"];
export type SelfBanChoice = "none" | SelfBanStatus;
export const SESSION_EVENTS: readonly SessionEventType[] = [
  "new_device",
  "access_recovery",
  "remote_control",
];

export interface FormState {
  channel: Channel;
  branchId: string;
  employeeId: string;
  pinfl: string;
  phone: string;
  deviceId: string;
  address: string;
  employerInn: string;
  amount: string;
  termMonths: string;
  purpose: string;
  account: string;
  helperId: string;
  supplierInn: string;
  supplierAccount: string;
  itemCode: string;
  unit: string;
  unitPrice: string;
  quantity: string;
  district: string;
  biometry: ApplicationDraft["checks"]["biometry"];
  phoneOwnerMatch: boolean;
  selfBan: SelfBanChoice;
  sessionEvents: readonly SessionEventType[];
}

export type TextKey = { [K in keyof FormState]: FormState[K] extends string ? K : never }[keyof FormState];

export const EMPTY_FORM: FormState = {
  channel: "online",
  branchId: "",
  employeeId: "",
  pinfl: "",
  phone: "",
  deviceId: "",
  address: "",
  employerInn: "",
  amount: "",
  termMonths: "",
  purpose: "",
  account: "",
  helperId: "",
  supplierInn: "",
  supplierAccount: "",
  itemCode: "",
  unit: "",
  unitPrice: "",
  quantity: "",
  district: "",
  biometry: "passed",
  phoneOwnerMatch: true,
  selfBan: "none",
  sessionEvents: [],
};

/** Путь поля в ошибках бэка (applicant.pinfl) → ключ формы. */
export const FIELD_PATHS: Readonly<Record<string, TextKey>> = {
  branch_id: "branchId",
  employee_id: "employeeId",
  "applicant.pinfl": "pinfl",
  "applicant.phone": "phone",
  "applicant.device_id": "deviceId",
  "applicant.address": "address",
  "applicant.employer_inn": "employerInn",
  "loan.amount": "amount",
  "loan.term_months": "termMonths",
  "loan.purpose": "purpose",
  disbursement_account: "account",
  "program.helper_id": "helperId",
  "program.supplier_inn": "supplierInn",
  "program.supplier_account": "supplierAccount",
  "program.item_code": "itemCode",
  "program.unit": "unit",
  "program.unit_price": "unitPrice",
  "program.quantity": "quantity",
  "program.district": "district",
};

export type FormErrors = Partial<Record<TextKey, string>>;

const REQUIRED_COMMON: readonly TextKey[] = ["branchId", "pinfl", "phone", "amount", "termMonths"];
const REQUIRED_BY_CHANNEL: Record<Channel, readonly TextKey[]> = {
  online: ["account"],
  program: [
    "helperId",
    "supplierInn",
    "supplierAccount",
    "itemCode",
    "unit",
    "unitPrice",
    "quantity",
    "district",
  ],
};
const NUMERIC: readonly TextKey[] = ["amount", "termMonths", "unitPrice", "quantity"];

export function validate(state: FormState): FormErrors {
  const errors: FormErrors = {};
  for (const key of [...REQUIRED_COMMON, ...REQUIRED_BY_CHANNEL[state.channel]]) {
    if (state[key].trim() === "") errors[key] = ru.conveyor.required;
  }
  for (const key of NUMERIC) {
    if (errors[key] === undefined && state[key].trim() !== "" && parseInteger(state[key]) === null) {
      errors[key] = ru.conveyor.notNumber;
    }
  }
  return errors;
}

const optional = (value: string): string | null => (value.trim() === "" ? null : value.trim());
const integer = (value: string): number => parseInteger(value) ?? 0;

export function toDraft(state: FormState, sessionRefs: string[]): ApplicationDraft {
  return {
    channel: state.channel,
    branch_id: state.branchId,
    employee_id: optional(state.employeeId),
    applicant: {
      pinfl: state.pinfl.trim(),
      phone: state.phone.trim(),
      device_id: optional(state.deviceId),
      address: optional(state.address),
      employer_inn: optional(state.employerInn),
    },
    loan: {
      amount: integer(state.amount),
      term_months: integer(state.termMonths),
      purpose: optional(state.purpose),
    },
    disbursement_account: state.channel === "online" ? state.account.trim() : null,
    program:
      state.channel === "program"
        ? {
            helper_id: state.helperId.trim(),
            supplier_inn: state.supplierInn.trim(),
            supplier_account: state.supplierAccount.trim(),
            item_code: state.itemCode.trim(),
            unit: state.unit.trim(),
            unit_price: integer(state.unitPrice),
            quantity: integer(state.quantity),
            district: state.district.trim(),
          }
        : null,
    checks: { biometry: state.biometry, phone_owner_match: state.phoneOwnerMatch },
    session_refs: sessionRefs,
  };
}

export function serverErrors(fields: Readonly<Record<string, string>>): FormErrors {
  const errors: FormErrors = {};
  for (const [path, message] of Object.entries(fields)) {
    const key = FIELD_PATHS[path];
    if (key !== undefined) errors[key] = message;
  }
  return errors;
}

/** Ошибки бэка без поля формы (например, «онлайн-заявке нужен счёт») — показываются общим списком. */
export function unmappedMessages(fields: Readonly<Record<string, string>>): string[] {
  return Object.entries(fields)
    .filter(([path]) => FIELD_PATHS[path] === undefined)
    .map(([, message]) => message);
}
