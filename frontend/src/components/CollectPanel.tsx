"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  COLLECT_FETCH_TIMEOUT_MS,
  getCollectSuggestions,
  getLlmStatus,
  postCollect,
  type CollectResult,
} from "@/lib/api";
import {
  COLLECT_APPLY_EVENT,
  clearStoredCollectPrefs,
  readStoredCollectPrefs,
  storeCollectSuggestions,
  type StoredCollectPrefs,
} from "@/lib/collectApply";

const CATS = [
  { slug: "data_analyst", label: "데이터 분석가" },
  { slug: "ai_engineer", label: "AI 엔지니어" },
  { slug: "backend_developer", label: "백엔드 개발자" },
];

const VALID_CATEGORY = new Set(["data_analyst", "ai_engineer", "backend_developer"]);

export function CollectPanel() {
  const [kw, setKw] = useState("Python, SQL");
  const [category, setCategory] = useState("data_analyst");
  const [saramin, setSaramin] = useState(true);
  const [jobkorea, setJobkorea] = useState(true);
  const [pages, setPages] = useState(1);
  const [detailOcr, setDetailOcr] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CollectResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [llm, setLlm] = useState<Awaited<ReturnType<typeof getLlmStatus>> | null>(null);
  const [collectPrefs, setCollectPrefs] = useState<StoredCollectPrefs | null>(null);
  const [collectSuggestLoading, setCollectSuggestLoading] = useState(false);
  const collectAbortRef = useRef<AbortController | null>(null);
  const collectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const applyCollectPrefs = useCallback((p: StoredCollectPrefs) => {
    setKw(p.keywordsLine);
    if (VALID_CATEGORY.has(p.category)) setCategory(p.category);
    setCollectPrefs(p);
  }, []);

  useEffect(() => {
    getLlmStatus().then(setLlm).catch(() => setLlm(null));
  }, []);

  useEffect(() => {
    const existing = readStoredCollectPrefs();
    if (existing) applyCollectPrefs(existing);
    const onApply = () => {
      const next = readStoredCollectPrefs();
      if (next) applyCollectPrefs(next);
    };
    window.addEventListener(COLLECT_APPLY_EVENT, onApply);
    return () => window.removeEventListener(COLLECT_APPLY_EVENT, onApply);
  }, [applyCollectPrefs]);

  function appendGapKeywords() {
    if (!collectPrefs?.gapKeywords.length) return;
    const add = collectPrefs.gapKeywords.join(", ");
    setKw((prev) => (prev.trim() ? `${prev.trim()}, ${add}` : add));
  }

  async function loadCollectSuggestionsFromProfile() {
    setCollectSuggestLoading(true);
    setErr(null);
    try {
      const s = await getCollectSuggestions();
      storeCollectSuggestions(s);
    } catch (x) {
      setErr(x instanceof Error ? x.message : "추천 불러오기 실패");
    } finally {
      setCollectSuggestLoading(false);
    }
  }

  function clearCollectTimeout() {
    if (collectTimerRef.current) {
      clearTimeout(collectTimerRef.current);
      collectTimerRef.current = null;
    }
  }

  function cancelCollect() {
    collectAbortRef.current?.abort();
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    collectAbortRef.current?.abort();
    clearCollectTimeout();
    setLoading(true);
    setErr(null);
    setResult(null);
    const keywords = kw
      .split(/[,，\n]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const sources: ("saramin" | "jobkorea")[] = [];
    if (saramin) sources.push("saramin");
    if (jobkorea) sources.push("jobkorea");
    const ac = new AbortController();
    collectAbortRef.current = ac;
    collectTimerRef.current = setTimeout(() => {
      ac.abort();
    }, COLLECT_FETCH_TIMEOUT_MS);
    try {
      const r = await postCollect(
        {
          keywords,
          category,
          sources,
          max_pages: pages,
          fetch_detail: detailOcr,
          use_ocr: detailOcr,
        },
        ac.signal
      );
      setResult(r);
    } catch (x) {
      const aborted =
        (typeof DOMException !== "undefined" &&
          x instanceof DOMException &&
          x.name === "AbortError") ||
        (x instanceof Error && x.name === "AbortError");
      if (aborted) {
        setErr(
          "요청이 취소되었거나 시간 초과(8분)입니다. 키워드·페이지 수를 줄이거나 상세 OCR을 끄세요. " +
            "계속 느리면 `.env`에 NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 처럼 백엔드 직접 주소를 넣어 Next 프록시를 우회해 보세요."
        );
      } else {
        setErr(x instanceof Error ? x.message : "요청 실패");
      }
    } finally {
      clearCollectTimeout();
      collectAbortRef.current = null;
      setLoading(false);
    }
  }

  return (
    <section id="collect-panel" className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
      <h2 className="text-lg font-semibold text-white">키워드로 채용 공고 수집</h2>
      <p className="mt-1 text-sm text-slate-400">
        사람인·잡코리아 검색 결과(목록)를 가져와 DB에 저장한 뒤 스킬·격차 분석을 갱신합니다. 동일
        공고는 소스+공고ID로 중복 제외됩니다. 이력서/PDF 분석 후에는 아래 추천 키워드·직군이 자동으로
        채워질 수 있습니다.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={collectSuggestLoading}
          onClick={loadCollectSuggestionsFromProfile}
          className="rounded-lg border border-emerald-800 bg-emerald-950/30 px-3 py-1.5 text-xs text-emerald-200 hover:bg-emerald-900/25 disabled:opacity-50"
        >
          {collectSuggestLoading ? "불러오는 중…" : "저장된 프로필 기준 수집 추천 적용"}
        </button>
      </div>

      {collectPrefs && (
        <div className="mt-3 rounded-lg border border-emerald-800/50 bg-emerald-950/15 p-3 text-sm">
          <p className="font-medium text-emerald-100/90">분석 기반 수집 설정</p>
          <p className="mt-1 text-xs text-slate-400">
            선택된 분석 직군 가산과 기술 스택·경력 연차를 반영한 검색어입니다. 실제 저장 직군은 3가지
            중 하나입니다.
          </p>
          <ol className="mt-2 space-y-1 text-xs text-slate-300">
            {collectPrefs.ranked.map((r, i) => (
              <li key={r.slug}>
                <span className="text-slate-500">{i + 1}순위</span> {r.label_ko}{" "}
                <span className="text-slate-500">(점수 {r.score})</span>
                {r.reasons.length > 0 && (
                  <span className="text-slate-500"> — {r.reasons.slice(0, 5).join(", ")}</span>
                )}
              </li>
            ))}
          </ol>
          {collectPrefs.notes.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-xs text-amber-200/85">
              {collectPrefs.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            {collectPrefs.gapKeywords.length > 0 && (
              <button
                type="button"
                onClick={appendGapKeywords}
                className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-200 hover:bg-slate-700"
              >
                갭 스킬 검색어 추가 ({collectPrefs.gapKeywords.join(", ")})
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                clearStoredCollectPrefs();
                setCollectPrefs(null);
              }}
              className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-500 hover:text-slate-300"
            >
              추천 안내 닫기
            </button>
          </div>
        </div>
      )}

      {llm && (
        <p className="mt-3 rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-2 text-xs text-slate-400">
          LLM: OpenAI 키 {llm.openai_configured ? "설정됨" : "없음"} · Ollama{" "}
          {llm.ollama_reachable ? (
            <span className="text-emerald-400">연결됨</span>
          ) : (
            <span className="text-amber-400">미응답 ({llm.ollama_model})</span>
          )}
          {(!llm.openai_configured && !llm.ollama_reachable) && (
            <span> — 추천 문장은 규칙 기반만 사용됩니다.</span>
          )}
        </p>
      )}

      <form onSubmit={onSubmit} className="mt-4 space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-500">검색 키워드 (쉼표/줄바꿈)</label>
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
            rows={2}
            value={kw}
            onChange={(e) => setKw(e.target.value)}
            placeholder="예: Python, 데이터분석"
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-slate-500">분석 직군</label>
            <select
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATS.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">키워드당 페이지 (각 사이트)</label>
            <input
              type="number"
              min={1}
              max={5}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
              value={pages}
              onChange={(e) => setPages(Number(e.target.value))}
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-4 text-sm text-slate-300">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={saramin} onChange={(e) => setSaramin(e.target.checked)} />
            사람인
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={jobkorea} onChange={(e) => setJobkorea(e.target.checked)} />
            잡코리아
          </label>
          <label className="flex max-w-xl items-start gap-2 border-l border-slate-700 pl-4">
            <input
              type="checkbox"
              checked={detailOcr}
              onChange={(e) => setDetailOcr(e.target.checked)}
            />
            <span>
              상세 페이지 + 이미지 OCR (한·영) — 공고마다 상세 HTML을 열고 이미지에서 텍스트 추출.
              <span className="text-amber-400"> 시간이 오래 걸릴 수 있습니다.</span>
            </span>
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={loading || (!saramin && !jobkorea)}
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {loading ? "수집 중…" : "수집 및 분석 실행"}
          </button>
          {loading && (
            <button
              type="button"
              onClick={cancelCollect}
              className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              취소
            </button>
          )}
          <span className="text-xs text-slate-500">
            사이트 응답에 따라 수 분~십여 분 걸릴 수 있습니다. 멈춘 것 같으면 취소 후 페이지·키워드를 줄이거나{" "}
            <code className="rounded bg-slate-900 px-1">NEXT_PUBLIC_API_URL</code>로 백엔드 직접 호출을
            쓰세요. (최대 약 8분 후 자동 중단)
          </span>
        </div>
      </form>

      {err && (
        <p className="mt-3 text-sm text-rose-400 whitespace-pre-wrap">{err}</p>
      )}
      {result && (
        <div className="mt-3 text-sm text-slate-300">
          <p>
            가져온 건수(중복 포함): <strong>{result.jobs_fetched}</strong> · 신규 저장:{" "}
            <strong>{result.jobs_new}</strong>
          </p>
          {result.errors.length > 0 && (
            <p className="mt-2 text-amber-400 text-xs">일부 오류: {result.errors.join(" | ")}</p>
          )}
          {(result.job_links ?? []).length > 0 && (
            <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950/60 p-3">
              <p className="text-xs font-medium text-slate-400">이번에 수집·저장된 공고 원본 링크</p>
              <ul className="mt-2 max-h-64 space-y-2 overflow-y-auto text-xs">
                {(result.job_links ?? []).map((row) => (
                  <li
                    key={row.id}
                    className="border-b border-slate-800/80 pb-2 last:border-0 last:pb-0"
                  >
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                      <span className="shrink-0 rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
                        {row.source}
                      </span>
                      <span className="font-medium text-slate-200">{row.title}</span>
                    </div>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-slate-500">
                      <span>{row.company}</span>
                      <Link
                        href={`/job/${row.id}`}
                        className="text-emerald-400 hover:underline"
                      >
                        키워드 분석 →
                      </Link>
                    </p>
                    {row.url ? (
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1 inline-block break-all text-sky-400 hover:underline"
                      >
                        {row.url}
                      </a>
                    ) : (
                      <p className="mt-1 text-slate-600">원본 URL 없음</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
