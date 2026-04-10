import Link from "next/link";
import { getAnalyzedKeywords, getOverview } from "@/lib/api";
import { CollectPanel } from "@/components/CollectPanel";
import { ResumeDashboardPanel } from "@/components/ResumeDashboardPanel";
import { JobCountBar } from "@/components/charts/JobCountBar";

export default async function HomePage() {
  let overview = null as Awaited<ReturnType<typeof getOverview>> | null;
  let analyzedKeywords = [] as Awaited<ReturnType<typeof getAnalyzedKeywords>>;
  let err = false;
  try {
    [overview, analyzedKeywords] = await Promise.all([
      getOverview(),
      getAnalyzedKeywords(60).catch(() => []),
    ]);
  } catch {
    err = true;
  }

  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <h1 className="text-2xl font-bold text-white md:text-3xl">
          채용 수요 × 검색 관심 — 교육·취업 인사이트
        </h1>
        <p className="max-w-3xl text-slate-400">
          단순 공고 나열이 아니라, <strong className="text-slate-200">채용에서 요구되는 역량</strong>
          과 <strong className="text-slate-200">대중의 검색 관심</strong>을 같은 축에서 비교합니다.
          데이터/AI/백엔드 직군 MVP 범위에서 과포화·기회 영역을 구분하고, 학원과 취준생에게 맞춤
          문장을 제시합니다.
        </p>
        <p className="text-sm">
          <Link href="/consultant" className="text-sky-400 hover:underline">
            컨설턴트 보드
          </Link>
          <span className="text-slate-500">
            {" "}
            — 여러 학생 일정·월간 목표 관리. 아래 이력서를 「프로필에 저장」한 뒤 보드에서 「대시보드 프로필 → 새
            학생」으로 가져올 수 있습니다.
          </span>
        </p>
      </section>

      {err && (
        <div className="rounded-lg border border-amber-600/50 bg-amber-950/40 px-4 py-3 text-amber-200">
          API에 연결할 수 없습니다. 백엔드를 실행했는지 확인하세요.{" "}
          <code className="rounded bg-slate-900 px-1">uvicorn app.main:app</code>
        </div>
      )}

      {overview && (
        <>
          <CollectPanel />

          <ResumeDashboardPanel />

          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              title="총 채용 공고(데모)"
              value={String(
                Object.values(overview.job_counts_by_category).reduce((a, b) => a + b, 0)
              )}
            />
            <MetricCard
              title="관심 급상승 키워드(샘플)"
              value={overview.rising_interest_keywords.slice(0, 3).join(", ") || "—"}
              small
            />
            <MetricCard
              title="기회 영역 키워드"
              value={overview.opportunity_keywords.slice(0, 3).join(", ") || "—"}
              small
            />
            <MetricCard
              title="과포화 가능성"
              value={overview.oversaturated_keywords.slice(0, 3).join(", ") || "—"}
              small
            />
          </section>

          <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <h2 className="mb-4 text-lg font-semibold text-white">직군별 채용 공고 수</h2>
            <JobCountBar data={overview.job_counts_by_category} />
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-white">직군 상세 분석</h2>
            <div className="flex flex-wrap gap-2">
              {[
                ["data_analyst", "데이터 분석가"],
                ["ai_engineer", "AI 엔지니어"],
                ["backend_developer", "백엔드 개발자"],
              ].map(([slug, label]) => (
                <Link
                  key={slug}
                  href={`/category/${slug}`}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-sky-300 hover:border-sky-600 hover:bg-slate-800"
                >
                  {label} →
                </Link>
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <h2 className="mb-2 text-lg font-semibold text-white">분석 완료 키워드 리스트</h2>
            <p className="mb-4 text-sm text-slate-400">
              키워드를 누르면 해당 공고를 연차/기업 위치 기준으로 정렬해 보여줍니다.
            </p>
            {analyzedKeywords.length === 0 ? (
              <p className="text-sm text-slate-500">표시할 키워드가 없습니다.</p>
            ) : (
              <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {analyzedKeywords.map((k) => (
                  <li key={k.keyword}>
                    <Link
                      href={`/keyword/${encodeURIComponent(k.keyword)}`}
                      className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm hover:border-sky-600 hover:bg-slate-800"
                    >
                      <span className="font-medium text-sky-300">{k.keyword}</span>
                      <span className="text-xs text-slate-500">
                        공고 {k.jobs_count} · 언급 {k.mentions_count}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function MetricCard({
  title,
  value,
  small,
}: {
  title: string;
  value: string;
  small?: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{title}</p>
      <p className={`mt-1 font-medium text-slate-100 ${small ? "text-sm leading-snug" : "text-2xl"}`}>
        {value}
      </p>
    </div>
  );
}
