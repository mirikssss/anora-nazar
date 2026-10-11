// Готовые сценарии трёх зон в имитаторе банка: каталог, запуск и прошлые запуски песочницы.
import { useQuery } from "@tanstack/react-query";

import { bankApi, request, type BankSchemas } from "@/shared/api";
import { str } from "@/shared/lib/json";

export type Scenario = BankSchemas["schemas"]["ScenarioOut"];
export type ScenarioRun = BankSchemas["schemas"]["ScenarioRunOut"];
export type RunApplication = BankSchemas["schemas"]["RunApplicationOut"];

export const scenarioKeys = {
  catalog: ["scenarios", "catalog"] as const,
  runs: ["scenarios", "runs"] as const,
};

export function useScenarios() {
  return useQuery({
    queryKey: scenarioKeys.catalog,
    queryFn: () => request(bankApi.GET("/v1/scenarios")),
    staleTime: Infinity,
  });
}

export function useScenarioRuns() {
  return useQuery({
    queryKey: scenarioKeys.runs,
    queryFn: () => request(bankApi.GET("/v1/scenarios/runs")),
  });
}

export function runScenario(code: string): Promise<ScenarioRun> {
  return request(bankApi.POST("/v1/scenarios/{code}/runs", { params: { path: { code } } }));
}

/** Последний запуск сценария в песочнице: у запусков сквозной номер. */
export function latestRun(runs: readonly ScenarioRun[], code: string): ScenarioRun | undefined {
  return runs
    .filter((run) => run.scenario_code === code)
    .reduce<ScenarioRun | undefined>(
      (last, run) => (last && last.number > run.number ? last : run),
      undefined,
    );
}

/** Идентификатор решения узла из ответа, сохранённого конвейером как JSON. */
export function runDecisionId(application: RunApplication): string | null {
  return str(application.last_decision?.decision_id);
}

/** Текст ошибки бэка по заявке сценария ({code, message}). */
export function runError(application: RunApplication): string | null {
  return application.error === null ? null : (str(application.error.message) ?? str(application.error.code));
}
