// Запросы конвейера имитатора банка: заявки песочницы, подача, новая версия, оценка, отмена.
import { useQuery } from "@tanstack/react-query";

import { bankApi, request } from "@/shared/api";

import type { Application, ApplicationChange, ApplicationDraft } from "./model";

export const applicationKeys = {
  all: ["applications"] as const,
};

export function useApplications() {
  return useQuery({
    queryKey: applicationKeys.all,
    queryFn: () => request(bankApi.GET("/v1/conveyor/applications")),
  });
}

export function submitApplication(draft: ApplicationDraft): Promise<Application> {
  return request(bankApi.POST("/v1/conveyor/applications", { body: draft }));
}

export function changeApplication(applicationId: string, change: ApplicationChange): Promise<Application> {
  return request(
    bankApi.PATCH("/v1/conveyor/applications/{application_id}", {
      params: { path: { application_id: applicationId } },
      body: change,
    }),
  );
}

export function reassessApplication(applicationId: string): Promise<Application> {
  return request(
    bankApi.POST("/v1/conveyor/applications/{application_id}/assessments", {
      params: { path: { application_id: applicationId } },
    }),
  );
}

export function cancelApplication(applicationId: string): Promise<Application> {
  return request(
    bankApi.POST("/v1/conveyor/applications/{application_id}/cancel", {
      params: { path: { application_id: applicationId } },
    }),
  );
}
