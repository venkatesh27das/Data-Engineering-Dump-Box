import { request } from "./projects";
import type { AssetFilters, AssetKind, AssetOverview, AssetPage, AssetView, ReviewStatus } from "../types/assets";

export function getAssetOverview(projectId: string, signal?: AbortSignal): Promise<AssetOverview> {
  return request<AssetOverview>(`/api/v1/projects/${projectId}/assets`, { signal });
}

export function listAssets(projectId: string, kind: AssetKind, filters: AssetFilters, page: number, signal?: AbortSignal): Promise<AssetPage> {
  const query = new URLSearchParams({ page: String(page), page_size: "10" });
  if (filters.search) query.set("search", filters.search);
  if (filters.assetType) query.set("asset_type", filters.assetType);
  if (filters.source) query.set("source", filters.source);
  if (filters.minimumConfidence) query.set("minimum_confidence", filters.minimumConfidence);
  if (filters.reviewStatus) query.set("review_status", filters.reviewStatus);
  return request<AssetPage>(`/api/v1/projects/${projectId}/assets/${kind}?${query}`, { signal });
}

export function reviewAsset(projectId: string, assetId: string, decision: "approve" | "review" | "reject", note?: string): Promise<{ asset: AssetView; decision: ReviewStatus }> {
  return request(`/api/v1/projects/${projectId}/assets/${assetId}/${decision}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: note || null }),
  });
}
