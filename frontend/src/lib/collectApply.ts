/** 분석 결과 → 공고 수집 폼으로 전달 (sessionStorage + 커스텀 이벤트). */

import type { CategoryFit, CollectSuggestions } from "./api";

export const COLLECT_APPLY_EVENT = "ilhaeseum-youth-maker:apply-collect";
const STORAGE_KEY = "ilhaeseum_youth_maker_collect_v1";

export type StoredCollectPrefs = {
  keywordsLine: string;
  category: string;
  ranked: CategoryFit[];
  notes: string[];
  gapKeywords: string[];
  ts: number;
};

export function storeCollectSuggestions(s: CollectSuggestions): void {
  if (typeof window === "undefined") return;
  const payload: StoredCollectPrefs = {
    keywordsLine: s.search_keywords.join(", "),
    category: s.primary_category_slug,
    ranked: s.category_ranked,
    notes: s.role_expansion_notes,
    gapKeywords: s.optional_gap_keywords,
    ts: Date.now(),
  };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  window.dispatchEvent(new Event(COLLECT_APPLY_EVENT));
}

export function readStoredCollectPrefs(): StoredCollectPrefs | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredCollectPrefs;
  } catch {
    return null;
  }
}

export function clearStoredCollectPrefs(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(STORAGE_KEY);
}
