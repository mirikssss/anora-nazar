// Каталог текстов узла (node/texts): формулировки причин, признаков, уровней, исходов — для сотрудника;
// шаблоны экранов и причин без названия признака — для заёмщика. Фронт текстов по кодам не хранит.
import { useQuery } from "@tanstack/react-query";

import { nodeApi, request, type NodeSchemas } from "@/shared/api";

export type StaffTexts = NodeSchemas["schemas"]["StaffTextsOut"];
export type ClientTexts = NodeSchemas["schemas"]["ClientTextsOut"];
export type ClientScreen = NodeSchemas["schemas"]["ClientScreenOut"];

export const textKeys = {
  staff: ["texts", "staff"] as const,
  client: ["texts", "client"] as const,
};

export function useStaffTexts() {
  return useQuery({
    queryKey: textKeys.staff,
    queryFn: async () => {
      const texts = await request(nodeApi.GET("/v1/texts", { params: { query: { audience: "staff" } } }));
      if (texts.audience !== "staff") throw new Error("Каталог вернул тексты не для сотрудника");
      return texts;
    },
    staleTime: Infinity,
  });
}

export function useClientTexts() {
  return useQuery({
    queryKey: textKeys.client,
    queryFn: async () => {
      const texts = await request(nodeApi.GET("/v1/texts", { params: { query: { audience: "client" } } }));
      if (texts.audience !== "client") throw new Error("Каталог вернул тексты не для заёмщика");
      return texts;
    },
    staleTime: Infinity,
  });
}

/** Заголовок по коду из раздела каталога; пока каталог грузится или кода нет — сам код. */
export function titleOf(
  section: Readonly<Record<string, { title: string }>> | undefined,
  code: string,
): string {
  return section?.[code]?.title ?? code;
}
