// Версии моделей, отчёт качества, выпуск со вторым подписантом и запуск обучения.
import { useQuery } from "@tanstack/react-query";

import { nodeApi, request, type NodeSchemas } from "@/shared/api";

export type ModelVersion = NodeSchemas["schemas"]["ModelVersionOut"];
export type Release = NodeSchemas["schemas"]["ReleaseOut"];
export type TrainingRun = NodeSchemas["schemas"]["TrainingRunOut"];

export const modelKeys = {
  versions: ["models"] as const,
  report: ["quality-report"] as const,
  releases: ["models", "releases"] as const,
  trainingRuns: ["models", "training-runs"] as const,
};

/** Прогон обучения идёт фоном: пока он не завершён, список опрашивается. */
const TRAINING_POLL_MS = 3000;
const FINISHED: ReadonlySet<TrainingRun["status"]> = new Set(["done", "failed"]);

export function isTrainingFinished(run: TrainingRun): boolean {
  return FINISHED.has(run.status);
}

export function useModelVersions(enabled = true) {
  return useQuery({
    queryKey: modelKeys.versions,
    queryFn: () => request(nodeApi.GET("/v1/models")),
    enabled,
  });
}

export function useQualityReport() {
  return useQuery({
    queryKey: modelKeys.report,
    queryFn: () => request(nodeApi.GET("/v1/quality/reports/latest")),
  });
}

export function usePendingReleases() {
  return useQuery({
    queryKey: modelKeys.releases,
    queryFn: () => request(nodeApi.GET("/v1/models/releases")),
  });
}

export function useTrainingRuns() {
  return useQuery({
    queryKey: modelKeys.trainingRuns,
    queryFn: () => request(nodeApi.GET("/v1/models/training-runs")),
    refetchInterval: (query) =>
      query.state.data?.every(isTrainingFinished) === false ? TRAINING_POLL_MS : false,
  });
}

export function requestRelease(modelId: string): Promise<Release> {
  return request(nodeApi.POST("/v1/models/{model_id}/releases", { params: { path: { model_id: modelId } } }));
}

export function approveRelease(releaseId: string): Promise<Release> {
  return request(
    nodeApi.POST("/v1/models/releases/{release_id}/approval", {
      params: { path: { release_id: releaseId } },
    }),
  );
}

export function requestTraining(): Promise<TrainingRun> {
  return request(nodeApi.POST("/v1/models/training-runs"));
}
