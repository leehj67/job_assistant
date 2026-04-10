import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getGap,
  getSkillStats,
  getTrendSeries,
  getRecommendations,
} from "@/lib/api";
import { TrendLine } from "@/components/charts/TrendLine";
import { DemandInterestCompare } from "@/components/charts/DemandInterestCompare";
import { GapCards } from "@/components/GapCards";

const LABELS: Record<string, string> = {
  data_analyst: "데이터 분석가",
  ai_engineer: "AI 엔지니어",
  backend_developer: "백엔드 개발자",
};

const DEFAULT_TREND_KW = ["Python", "SQL", "머신러닝", "Docker", "생성형 AI"];

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (!LABELS[slug]) notFound();

  const [gap, skills, trendSeries, recAcademy, recJob] = await Promise.all([
    getGap(slug),
    getSkillStats(slug),
    getTrendSeries(slug, DEFAULT_TREND_KW),
    getRecommendations(slug, "academy"),
    getRecommendations(slug, "jobseeker"),
  ]);

  return (
    <div className="space-y-10">
      <div>
        <Link href="/" className="text-sm text-sky-400 hover:underline">
          ← 대시보드
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-white">{LABELS[slug]}</h1>
        <p className="mt-1 text-slate-400">
          채용 공고 기반 수요 점수와 검색 트렌드 관심도를 비교합니다.
        </p>
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="mb-2 text-lg font-semibold text-white">상위 역량 키워드 (공고 기준)</h2>
        <ul className="flex flex-wrap gap-2">
          {skills.slice(0, 15).map((s) => (
            <li
              key={s.normalized_skill}
              className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300"
            >
              {s.normalized_skill}{" "}
              <span className="text-slate-500">({s.count})</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="mb-4 text-lg font-semibold text-white">기술 키워드 관심도 추이</h2>
        <p className="mb-2 text-xs text-slate-500">
          샘플 키워드: {DEFAULT_TREND_KW.join(", ")}
        </p>
        <TrendLine series={trendSeries} />
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="mb-4 text-lg font-semibold text-white">수요 vs 관심도 비교</h2>
        <DemandInterestCompare items={gap} />
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold text-white">격차 분류</h2>
        <GapCards items={gap} />
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <h3 className="mb-2 font-semibold text-emerald-300">교육기관용 요약</h3>
          {recAcademy[0] ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
              {recAcademy[0].content}
            </p>
          ) : (
            <p className="text-slate-500">추천 데이터 없음</p>
          )}
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <h3 className="mb-2 font-semibold text-sky-300">취준생용 요약</h3>
          {recJob[0] ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
              {recJob[0].content}
            </p>
          ) : (
            <p className="text-slate-500">추천 데이터 없음</p>
          )}
        </div>
      </section>
    </div>
  );
}
