"use client";

import { useState } from "react";
import { postResumeInsight, type ResumeInsight } from "@/lib/api";
import { storeCollectSuggestions } from "@/lib/collectApply";

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

  async function run() {
    setLoading(true);
    setErr(null);
    try {
      const r = await postResumeInsight({
        resume_text: props.resumeText,
        career_summary: props.careerSummary,
        category: props.category === "all" ? null : props.category,
      });
      setData(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "분석 실패");
    } finally {
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
