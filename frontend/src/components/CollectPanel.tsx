"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  COLLECT_STREAM_IDLE_MS,
  getCategories,
  getCollectSourcesHealth,
  getCollectSuggestions,
  getLlmStatus,
  postApplicantAnalysisCategory,
  postCollectStream,
  type CategoryItem,
  type CollectResult,
  type CollectSourcesHealth,
} from "@/lib/api";
import {
  COLLECT_APPLY_EVENT,
  clearStoredCollectPrefs,
  readStoredCollectPrefs,
  storeCollectSuggestions,
  type StoredCollectPrefs,
} from "@/lib/collectApply";

export function CollectPanel() {
  const [cats, setCats] = useState<CategoryItem[]>([]);
  const catSlugs = useMemo(() => new Set(cats.map((c) => c.slug)), [cats]);
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
  const [sourcesHealth, setSourcesHealth] = useState<CollectSourcesHealth | null>(null);
  const [sourcesHealthLoading, setSourcesHealthLoading] = useState(false);
  const [sourcesHealthErr, setSourcesHealthErr] = useState<string | null>(null);
  const [collectPrefs, setCollectPrefs] = useState<StoredCollectPrefs | null>(null);
  const [collectSuggestLoading, setCollectSuggestLoading] = useState(false);
  const [progressPct, setProgressPct] = useState(0);
  const [progressHint, setProgressHint] = useState("");
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const collectAbortRef = useRef<AbortController | null>(null);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelKindRef = useRef<"user" | "idle" | null>(null);
  const [newRoleLabel, setNewRoleLabel] = useState("");
  const [newRoleKeywords, setNewRoleKeywords] = useState("");
  const [addingRole, setAddingRole] = useState(false);

  const applyCollectPrefs = useCallback(
    (p: StoredCollectPrefs) => {
      setKw(p.keywordsLine);
      setCategory((prev) => (catSlugs.has(p.category) ? p.category : prev));
      setCollectPrefs(p);
    },
    [catSlugs]
  );

  useEffect(() => {
    getCategories()
      .then(setCats)
      .catch(() => setCats([]));
  }, []);

  useEffect(() => {
    if (cats.length > 0 && !catSlugs.has(category)) {
      setCategory(cats[0].slug);
    }
  }, [cats, catSlugs, category]);

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

  async function runSourcesHealthCheck() {
    setSourcesHealthLoading(true);
    setSourcesHealthErr(null);
    try {
      const h = await getCollectSourcesHealth();
      setSourcesHealth(h);
    } catch (x) {
      setSourcesHealth(null);
      setSourcesHealthErr(x instanceof Error ? x.message : "연결 확인 실패");
    } finally {
      setSourcesHealthLoading(false);
    }
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

  function clearIdleTimer() {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
  }

  function cancelCollect() {
    cancelKindRef.current = "user";
    collectAbortRef.current?.abort();
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    collectAbortRef.current?.abort();
    clearIdleTimer();
    setLoading(true);
    setErr(null);
    setResult(null);
    setProgressPct(0);
    setProgressHint("");
    setProgressLog([]);
    cancelKindRef.current = null;
    const keywords = kw
      .split(/[,，\n]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const sources: ("saramin" | "jobkorea")[] = [];
    if (saramin) sources.push("saramin");
    if (jobkorea) sources.push("jobkorea");
    const ac = new AbortController();
    collectAbortRef.current = ac;

    const bumpIdle = () => {
      clearIdleTimer();
      idleTimerRef.current = setTimeout(() => {
        cancelKindRef.current = "idle";
        ac.abort();
      }, COLLECT_STREAM_IDLE_MS);
    };
    bumpIdle();

    const pushLog = (line: string) => {
      setProgressLog((prev) => [...prev, line].slice(-14));
    };

    try {
      const r = await postCollectStream(
        {
          keywords,
          category,
          sources,
          max_pages: pages,
          fetch_detail: detailOcr,
          use_ocr: detailOcr,
        },
        {
          signal: ac.signal,
          onEvent: (raw) => {
            bumpIdle();
            if (!raw || typeof raw !== "object") return;
            const ev = raw as Record<string, unknown>;
            const typ = ev.type;
            if (typ === "start") {
              const tot = typeof ev.total_page_batches === "number" ? ev.total_page_batches : 0;
              const srcs = Array.isArray(ev.sources) ? (ev.sources as string[]).join(", ") : "";
              setProgressPct(0);
              setProgressHint(`${srcs || "수집"} · 총 ${tot}페이지 단위`);
              pushLog(`시작 · ${tot}단계 · 상세=${Boolean(ev.fetch_detail)}`);
            } else if (typ === "progress") {
              const ph = String(ev.phase ?? "");
              if (ph === "connecting") {
                setProgressHint("서버 응답 수신 · 수집 스레드 시작…");
                pushLog("연결됨");
              } else if (ph === "fetch_list") {
                setProgressHint(
                  `${ev.source} · "${ev.keyword}" 목록 p${ev.page} 요청…`
                );
                pushLog(`목록 ${ev.source} "${ev.keyword}" p${ev.page}`);
              } else if (ph === "detail_row") {
                setProgressHint(
                  `${ev.source} · "${ev.keyword}" 상세 ${ev.row}/${ev.rows_total}`
                );
                const done = ev.page_batches_total
                  ? Math.min(
                      99,
                      ((Number(ev.page_batches_done) || 0) / Number(ev.page_batches_total)) * 100
                    )
                  : 0;
                setProgressPct(done);
                if ((Number(ev.row) || 0) % 5 === 1) {
                  pushLog(`상세 ${ev.source} "${ev.keyword}" ${ev.row}/${ev.rows_total}`);
                }
              } else if (ph === "page_done") {
                const tot = Number(ev.page_batches_total) || 1;
                const done = Number(ev.page_batches_done) || 0;
                setProgressPct(Math.min(100, (done / tot) * 100));
                setProgressHint(
                  `${ev.source} · "${ev.keyword}" p${ev.page} 저장 (${ev.new_ids_this_page}건 신규)`
                );
                pushLog(
                  `페이지 완료 ${ev.source} "${ev.keyword}" p${ev.page} · 이번페이지 신규 ${ev.new_ids_this_page} · 누적 신규 ${ev.jobs_new_so_far}`
                );
              }
            } else if (typ === "done" || typ === "cancelled") {
              setProgressPct(100);
              setProgressHint(typ === "cancelled" ? "중단됨 · 반영분 분석까지 수행" : "완료");
              pushLog(typ === "cancelled" ? "취소/연결 종료 — 부분 반영" : "완료");
            }
          },
        }
      );
      setResult(r);
    } catch (x) {
      const aborted =
        (typeof DOMException !== "undefined" &&
          x instanceof DOMException &&
          x.name === "AbortError") ||
        (x instanceof Error && x.name === "AbortError");
      if (aborted) {
        if (cancelKindRef.current === "idle") {
          setErr(
            `진행 알림이 ${Math.round(COLLECT_STREAM_IDLE_MS / 60000)}분 이상 없어 중단했습니다. 백엔드·네트워크를 확인하거나 상세 OCR을 끄고 다시 시도해 보세요.`
          );
        } else {
          setErr(
            "수집을 취소했습니다. 이미 처리된 페이지까지의 공고는 서버 DB에 반영되었을 수 있습니다."
          );
        }
      } else {
        setErr(x instanceof Error ? x.message : "요청 실패");
      }
    } finally {
      clearIdleTimer();
      collectAbortRef.current = null;
      setLoading(false);
    }
  }

  async function onAddRole(e: React.FormEvent) {
    e.preventDefault();
    const label = newRoleLabel.trim();
    if (!label) {
      setErr("직군 이름을 입력하세요.");
      return;
    }
    setAddingRole(true);
    setErr(null);
    try {
      const row = await postApplicantAnalysisCategory({
        label,
        keywords: newRoleKeywords,
      });
      const next = await getCategories();
      setCats(next);
      setCategory(row.slug);
      setNewRoleLabel("");
      setNewRoleKeywords("");
    } catch (x) {
      setErr(x instanceof Error ? x.message : "직군 추가 실패");
    } finally {
      setAddingRole(false);
    }
  }

  const selectedCat = cats.find((c) => c.slug === category);

  return (
    <section id="collect-panel" className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
      <h2 className="text-lg font-semibold text-white">키워드로 채용 공고 수집</h2>
      <p className="mt-1 text-sm text-slate-400">
        사람인·잡코리아 검색 결과(목록)를 가져와 DB에 저장한 뒤 스킬·격차 분석을 갱신합니다. 동일
        공고는 소스+공고ID로 중복 제외됩니다. 기본 직군 외에도 아래에서 직군을 추가하면 해당 슬러그로
        공고가 저장되고, 수집 시 등록 키워드·유사어가 검색어에 자동으로 합쳐집니다.
      </p>

      <div className="mt-4 rounded-lg border border-violet-900/40 bg-violet-950/15 p-3">
        <p className="text-xs font-medium text-violet-200/90">분석 직군 추가</p>
        <p className="mt-1 text-xs text-slate-500">
          직군 이름과(선택) 검색 키워드를 넣으면 유사 검색어가 붙습니다. 공고가 아직 없을 때는 같은
          키워드로 제목·검색어에 걸린 다른 직군 공고도 함께 보여 줍니다.
        </p>
        <form onSubmit={onAddRole} className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1">
            <label className="text-[11px] text-slate-500">직군 이름</label>
            <input
              className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-200"
              value={newRoleLabel}
              onChange={(e) => setNewRoleLabel(e.target.value)}
              placeholder="예: 프론트엔드"
            />
          </div>
          <div className="min-w-0 flex-[1.3]">
            <label className="text-[11px] text-slate-500">검색 키워드 (쉼표)</label>
            <input
              className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-200"
              value={newRoleKeywords}
              onChange={(e) => setNewRoleKeywords(e.target.value)}
              placeholder="예: React, 웹개발"
            />
          </div>
          <button
            type="submit"
            disabled={addingRole}
            className="shrink-0 rounded-lg border border-violet-600 bg-violet-900/40 px-3 py-2 text-xs text-violet-100 hover:bg-violet-800/40 disabled:opacity-50"
          >
            {addingRole ? "추가 중…" : "직군 등록"}
          </button>
        </form>
      </div>

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
            선택된 분석 직군 가산과 기술 스택·경력 연차를 반영한 검색어입니다. 저장 직군은 기본 3종
            가산에 가깝지만, 사용자 등록 직군을 고르면 해당 키워드가 수집에 반영됩니다.
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

      <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-xs">
        <span className="text-slate-500">수집 사이트(목록 1페이지 스모크, DB 미저장)</span>
        <button
          type="button"
          disabled={sourcesHealthLoading}
          onClick={runSourcesHealthCheck}
          className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-slate-200 hover:bg-slate-700 disabled:opacity-50"
        >
          {sourcesHealthLoading ? "확인 중…" : "연결 확인"}
        </button>
        {sourcesHealth && (
          <span className="flex flex-wrap gap-x-3 gap-y-1 text-slate-300">
            <span>
              사람인:{" "}
              {sourcesHealth.saramin.ok ? (
                <span className="text-emerald-400">
                  OK ({sourcesHealth.saramin.listings}건 / {sourcesHealth.saramin.ms}ms)
                </span>
              ) : (
                <span className="text-rose-400" title={sourcesHealth.saramin.error}>
                  실패
                </span>
              )}
            </span>
            <span>
              잡코리아:{" "}
              {sourcesHealth.jobkorea.ok ? (
                <span className="text-emerald-400">
                  OK ({sourcesHealth.jobkorea.listings}건 / {sourcesHealth.jobkorea.ms}ms)
                </span>
              ) : (
                <span className="text-rose-400" title={sourcesHealth.jobkorea.error}>
                  실패
                </span>
              )}
            </span>
          </span>
        )}
        {sourcesHealthErr && <span className="text-rose-400">{sourcesHealthErr}</span>}
      </div>

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
              {(cats.length ? cats : [{ slug: "data_analyst", label: "데이터 분석가" }]).map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label}
                  {c.orphan_job_bucket ? " · 공고만" : ""}
                </option>
              ))}
            </select>
            {selectedCat &&
              (selectedCat.primary_keywords?.length || selectedCat.similar_keywords?.length) ? (
              <p className="mt-1 text-[11px] text-slate-500">
                등록 키워드: {(selectedCat.primary_keywords ?? []).join(", ") || "—"}
                {(selectedCat.similar_keywords ?? []).length > 0 && (
                  <>
                    {" "}
                    · 유사: {(selectedCat.similar_keywords ?? []).slice(0, 8).join(", ")}
                  </>
                )}
              </p>
            ) : null}
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
            진행률은 NDJSON 스트림으로 표시됩니다. 진행 이벤트가 끊기면 약 {Math.round(COLLECT_STREAM_IDLE_MS / 60000)}분 후
            자동 중단합니다(정상 진행 중에는 고정 8분 제한 없음). 로컬은{" "}
            <code className="rounded bg-slate-900 px-1">NEXT_PUBLIC_API_URL</code>로 백엔드 직접 호출을 권장합니다.
          </span>
        </div>
      </form>

      {loading && (
        <div className="mt-4 space-y-2 rounded-lg border border-slate-700 bg-slate-950/60 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
            <span className="min-w-0 flex-1 truncate text-slate-300">{progressHint || "연결 중…"}</span>
            <span className="shrink-0 font-mono text-sky-400">{Math.round(progressPct)}%</span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-600 to-emerald-500 transition-[width] duration-500 ease-out"
              style={{ width: `${Math.max(2, progressPct)}%` }}
            />
          </div>
          <ul className="max-h-32 space-y-0.5 overflow-y-auto font-mono text-[10px] leading-snug text-slate-500">
            {progressLog.map((ln, i) => (
              <li key={`${i}-${ln.slice(0, 24)}`}>{ln}</li>
            ))}
          </ul>
        </div>
      )}

      {err && (
        <p className="mt-3 text-sm text-rose-400 whitespace-pre-wrap">{err}</p>
      )}
      {result && (
        <div className="mt-3 text-sm text-slate-300">
          {result.cancelled && (
            <p className="mb-2 rounded border border-amber-800/60 bg-amber-950/30 px-2 py-1.5 text-xs text-amber-200">
              일부만 수집된 뒤 중단되었습니다. 위 건수는 이미 DB에 반영된 분량입니다.
            </p>
          )}
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
