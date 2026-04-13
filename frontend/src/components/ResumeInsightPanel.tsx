"use client";

import { useEffect, useRef, useState } from "react";
import { postResumeInsight, type ResumeInsight } from "@/lib/api";
import { storeCollectSuggestions } from "@/lib/collectApply";

const INSIGHT_STEPS: { label: string; hint: string; log: string }[] = [
  {
    label: "이력서",
    hint: "1단계: 이력서·경력 요약 정규화 및 직군 컨텍스트 로드",
    log: "이력서 텍스트 수신 · 분석 직군 매핑",
  },
  {
    label: "시장 메트릭",
    hint: "2단계: 공고·트렌드 DB에서 수요·관심·메타 집계",
    log: "시장 수요·관심 지표와 공고 메타 교차",
  },
  {
    label: "스킬 매칭",
    hint: "3단계: 이력서 스킬 vs 시장 상위 스킬 갭·차별화 계산",
    log: "갭 영향도 · 차별화 자산 스코어링",
  },
  {
    label: "인사이트 합성",
    hint: "4단계: LLM 또는 규칙 기반으로 요약·액션 플랜 생성",
    log: "추천 문장·수집 키워드 후보 생성",
  },
];

const CAT_KO: Record<string, string> = {
  data_analyst: "데이터 분석가",
  ai_engineer: "AI 엔지니어",
  backend_developer: "백엔드 개발자",
};

export function ResumeInsightPanel(props: {
  resumeText: string;
  careerSummary: string;
  category: string;
  /** 공고 수집란 반영 후 상단 알림 등 */
  onCollectApplied?: (detail: string) => void;
}) {
  const [data, setData] = useState<ResumeInsight | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [progressPct, setProgressPct] = useState(0);
  const [progressHint, setProgressHint] = useState("");
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [activeStep, setActiveStep] = useState(0);
  const stepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (stepTimerRef.current) {
        clearInterval(stepTimerRef.current);
        stepTimerRef.current = null;
      }
    };
  }, []);

  function startInsightProgressTimers() {
    if (stepTimerRef.current) {
      clearInterval(stepTimerRef.current);
      stepTimerRef.current = null;
    }
    setActiveStep(0);
    setProgressPct(6);
    setProgressHint(INSIGHT_STEPS[0].hint);
    setProgressLog([INSIGHT_STEPS[0].log]);

    let stepIdx = 0;
    stepTimerRef.current = setInterval(() => {
      if (stepIdx >= INSIGHT_STEPS.length - 1) return;
      stepIdx += 1;
      setActiveStep(stepIdx);
      const s = INSIGHT_STEPS[stepIdx];
      setProgressHint(s.hint);
      setProgressLog((prev) => [...prev, s.log].slice(-14));
      const pct = Math.min(82, Math.round(((stepIdx + 1) / INSIGHT_STEPS.length) * 78) + 4);
      setProgressPct(pct);
    }, 1000);
  }

  function stopInsightProgressTimers() {
    if (stepTimerRef.current) {
      clearInterval(stepTimerRef.current);
      stepTimerRef.current = null;
    }
  }

  async function run() {
    setLoading(true);
    setErr(null);
    setData(null);
    startInsightProgressTimers();
    try {
      const r = await postResumeInsight({
        resume_text: props.resumeText,
        career_summary: props.careerSummary,
        category: props.category === "all" ? null : props.category,
      });
      stopInsightProgressTimers();
      setActiveStep(INSIGHT_STEPS.length - 1);
      setProgressPct(100);
      setProgressHint("완료 · 시장 인사이트 카드 반영");
      setProgressLog((prev) => [...prev, "응답 수신 · UI 갱신"].slice(-14));
      setData(r);
    } catch (e) {
      stopInsightProgressTimers();
      setProgressPct(0);
      setProgressHint("");
      setProgressLog([]);
      setActiveStep(0);
      setErr(e instanceof Error ? e.message : "분석 실패");
    } finally {
      stopInsightProgressTimers();
      setLoading(false);
    }
  }

  function applyInsightToCollectPanel() {
    if (!data?.collect_suggestions) return;
    storeCollectSuggestions(data.collect_suggestions);
    const s = data.collect_suggestions;
    props.onCollectApplied?.(
      `${s.primary_category_label_ko} · 키워드 ${s.search_keywords.length}개`
    );
    document.getElementById("collect-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const fitCat =
    data?.summary.market_fit_category_label ??
    CAT_KO[data?.summary.market_fit_category_slug ?? ""] ??
    data?.summary.current_best_fit_category;

  return (
    <div className="mt-6 space-y-4 border-t border-slate-800 pt-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-white">시장 인사이트</h3>
          <p className="text-xs text-slate-500">
            수요·관심·공고 메타(자격/우대/담당)와 이력서 스킬을 조합한 해석입니다. 생성 후 「공고 수집란에
            반영」으로 상단 수집 폼에 키워드·직군을 채울 수 있습니다.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={loading || (!props.resumeText.trim() && !props.careerSummary.trim())}
            onClick={run}
            className="rounded-lg border border-indigo-700 bg-indigo-950/50 px-4 py-2 text-sm text-indigo-200 hover:bg-indigo-900/40 disabled:opacity-50"
          >
            {loading ? "분석 중…" : "인사이트 생성"}
          </button>
          <button
            type="button"
            disabled={!data?.collect_suggestions}
            onClick={applyInsightToCollectPanel}
            className="rounded-lg border border-teal-800 bg-teal-950/40 px-4 py-2 text-sm text-teal-200 hover:bg-teal-900/30 disabled:opacity-50"
          >
            공고 수집란에 반영
          </button>
        </div>
      </div>

      {err && (
        <p className="rounded border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {err}
        </p>
      )}

      {loading && (
        <div className="space-y-3 rounded-lg border border-slate-700 bg-slate-950/60 p-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
            시장 인사이트 · 분석 단계
          </p>
          <ol className="flex flex-wrap items-center gap-1 text-[11px] sm:flex-nowrap sm:gap-0">
            {INSIGHT_STEPS.map((st, i) => {
              const done = i < activeStep;
              const on = i === activeStep;
              return (
                <li key={st.label} className="flex min-w-0 flex-1 items-center">
                  <div className="flex min-w-0 flex-col items-center gap-0.5 sm:flex-1">
                    <span
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold ${
                        on
                          ? "border-sky-500 bg-sky-600/30 text-sky-100 shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                          : done
                            ? "border-emerald-700/80 bg-emerald-950/50 text-emerald-200"
                            : "border-slate-700 bg-slate-900 text-slate-500"
                      }`}
                    >
                      {done ? "✓" : i + 1}
                    </span>
                    <span
                      className={`hidden max-w-[5.5rem] truncate text-center sm:block ${
                        on ? "text-sky-200" : done ? "text-emerald-200/90" : "text-slate-500"
                      }`}
                    >
                      {st.label}
                    </span>
                  </div>
                  {i < INSIGHT_STEPS.length - 1 && (
                    <div
                      className={`mx-0.5 hidden h-0.5 min-w-[12px] flex-1 sm:block ${
                        done ? "bg-emerald-700/60" : "bg-slate-800"
                      }`}
                      aria-hidden
                    />
                  )}
                </li>
              );
            })}
          </ol>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
            <span className="min-w-0 flex-1 truncate text-slate-300">{progressHint || "연결 중…"}</span>
            <span className="shrink-0 font-mono text-indigo-300">{Math.round(progressPct)}%</span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-emerald-500 transition-[width] duration-500 ease-out"
              style={{ width: `${Math.max(2, progressPct)}%` }}
            />
          </div>
          <ul className="max-h-32 space-y-0.5 overflow-y-auto font-mono text-[10px] leading-snug text-slate-500">
            {progressLog.map((ln, i) => (
              <li key={`${i}-${ln.slice(0, 28)}`}>{ln}</li>
            ))}
          </ul>
        </div>
      )}

      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <InsightCard title="시장 적합도" accent="border-sky-700/60 bg-sky-950/20">
            <p className="text-2xl font-semibold text-sky-200">
              {data.summary.market_fit_score}%
            </p>
            <p className="mt-2 text-sm text-slate-300">
              현재 이력서는 「{fitCat ?? "—"}」 직군 핵심 요구 스킬 상위 묶음 대비{" "}
              <strong className="text-white">{data.summary.market_fit_score}%</strong> 충족으로
              집계되었습니다.
            </p>
            <p className="mt-2 text-xs text-slate-500">{data.market_positioning.fit_reason}</p>
            <p className="mt-1 text-xs font-medium text-slate-400">
              포지션 라벨: {data.market_positioning.fit_label}
            </p>
          </InsightCard>

          <InsightCard title="영향도 높은 갭 (상위 3)" accent="border-amber-700/60 bg-amber-950/20">
            <ol className="list-inside list-decimal space-y-2 text-sm text-slate-300">
              {data.high_impact_gaps.slice(0, 3).map((g) => (
                <li key={g.skill}>
                  <span className="font-medium text-amber-100">{g.skill}</span>
                  <span className="text-slate-500">
                    {" "}
                    · 영향 {g.impact_score} · 수요 {g.demand_score ?? "—"}
                  </span>
                </li>
              ))}
            </ol>
            {data.high_impact_gaps.length === 0 && (
              <p className="text-sm text-slate-500">갭 데이터가 없거나 이미 대부분 충족입니다.</p>
            )}
          </InsightCard>

          <InsightCard title="차별화 자산" accent="border-emerald-700/60 bg-emerald-950/20">
            <ul className="space-y-2 text-sm text-slate-300">
              {data.differentiator_assets.slice(0, 6).map((a) => (
                <li key={a.skill}>
                  <span className="font-medium text-emerald-200">{a.skill}</span>
                  <span className="text-xs text-slate-500">
                    {" "}
                    (수요 {a.demand_score} / 관심 {a.interest_score})
                  </span>
                  {a.reason && <p className="text-xs text-slate-500">{a.reason}</p>}
                </li>
              ))}
            </ul>
            {data.differentiator_assets.length === 0 && (
              <p className="text-sm text-slate-500">조건에 맞는 항목이 없습니다.</p>
            )}
          </InsightCard>

          <InsightCard title="커리어 경로" accent="border-violet-700/60 bg-violet-950/20">
            <ul className="space-y-2 text-sm text-slate-300">
              {data.path_recommendations.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
            {data.summary.adjacent_categories.length > 0 && (
              <p className="mt-3 text-xs text-slate-500">
                인접 직군:{" "}
                {data.summary.adjacent_categories.map((a) => a.label_ko).join(", ")}
              </p>
            )}
          </InsightCard>

          <InsightCard title="즉시 · 중기 · 전략 액션" accent="border-slate-600 bg-slate-950/40 lg:col-span-2">
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <p className="text-xs font-medium text-sky-400">즉시 (1~2주)</p>
                <ul className="mt-1 list-inside list-disc text-sm text-slate-400">
                  {data.action_plan.immediate_actions.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-xs font-medium text-amber-400">중기 (1~2개월)</p>
                <ul className="mt-1 list-inside list-disc text-sm text-slate-400">
                  {data.action_plan.mid_term_actions.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-xs font-medium text-violet-400">전략</p>
                <ul className="mt-1 list-inside list-disc text-sm text-slate-400">
                  {data.action_plan.strategy_actions.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            </div>
          </InsightCard>

          {(data.optional_gaps.length > 0 || data.differentiator_gaps.length > 0) && (
            <InsightCard title="우대형 갭 · 차별화 기회(수요↑관심↓)" accent="border-slate-700 bg-slate-950/30 lg:col-span-2">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs text-slate-500">우대 비중 갭</p>
                  <ul className="mt-1 text-sm text-slate-400">
                    {data.optional_gaps.slice(0, 4).map((x) => (
                      <li key={String((x as { skill?: string }).skill)}>
                        {(x as { skill?: string }).skill}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs text-slate-500">기회 영역(시장 요약)</p>
                  <ul className="mt-1 text-sm text-slate-400">
                    {data.differentiator_gaps.slice(0, 4).map((x) => (
                      <li key={String((x as { skill?: string }).skill)}>
                        {(x as { skill?: string }).skill}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </InsightCard>
          )}

          <div className="lg:col-span-2 rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-xs text-slate-500">
            <p className="font-medium text-slate-400">강점 요약</p>
            <ul className="mt-1 list-inside list-disc">
              {data.core_strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function InsightCard({
  title,
  children,
  accent,
}: {
  title: string;
  children: React.ReactNode;
  accent: string;
}) {
  return (
    <div className={`rounded-xl border p-4 ${accent}`}>
      <h4 className="text-sm font-semibold text-slate-200">{title}</h4>
      <div className="mt-2">{children}</div>
    </div>
  );
}
