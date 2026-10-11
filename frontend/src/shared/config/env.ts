// Адреса API и параметры из переменных сборки (compose). Без значений приложение не стартует.
function required(name: string): string {
  const value: unknown = import.meta.env[name];
  if (typeof value !== "string" || value === "") {
    throw new Error(`Не задана переменная сборки ${name}`);
  }
  return value;
}

export const env = {
  nodeApiBase: required("VITE_NODE_API_BASE"),
  bankApiBase: required("VITE_BANK_API_BASE"),
  /** Часовой пояс банка: даты и время показываются в нём, а не в поясе устройства. */
  timeZone: required("VITE_TIME_ZONE"),
} as const;
