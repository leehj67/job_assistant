import Link from "next/link";
import { getCategories, getRecommendations, getGap } from "@/lib/api";

export default async function AcademyPage({
  searchParams,
}: {
  searchParams: Promise<{ cat?: string }>;
}) {
  const { cat = "data_analyst" } = await searchParams;
  const categories = await getCategories().catch(() => [] as { slug: string; label: string }[]);
  const rec = await getRecommendations(cat, "academy").catch(() => []);
  const gap = await getGap(cat).catch(() => []);

  const opportunity = gap.filter((g) => g.gap_type === "opportunity");
  const stable = gap.filter((g) => g.gap_type === "stable_hot");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">교육기관용 인사이트</h1>
        <p className="mt-1 text-slate-400">
          신규 강의 주제, 커리큘럼 보완, 시장 핵심 역량을 데모 데이터로 제시합니다.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {categories.map((c) => (
          <Link
            key={c.slug}
            href={`/academy?cat=${c.slug}`}
            className={`rounded-lg border px-3 py-1 text-sm ${
              cat === c.slug
                ? "border-emerald-500 bg-emerald-950/50 text-emerald-200"
                : "border-slate-700 text-slate-300 hover:border-slate-500"
            }`}
          >
            {c.label}
          </Link>
        ))}
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-emerald-300">신규 강의 후보</h2>
          <p className="mt-2 text-sm text-slate-300">
            수요는 높고 관심은 상대적으로 낮은 키워드:{" "}
            {opportunity.slice(0, 5).map((x) => x.keyword).join(", ") || "—"}
          </p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-emerald-300">커리큘럼에 넣을 핵심</h2>
          <p className="mt-2 text-sm text-slate-300">
            수요·관심 모두 높은 안정 영역:{" "}
            {stable.slice(0, 5).map((x) => x.keyword).join(", ") || "—"}
          </p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-emerald-300">보완이 필요한 영역</h2>
          <p className="mt-2 text-sm text-slate-300">
            관심만 높은 키워드는 실무 프로젝트와 묶어 설계하세요 (과포화 구간 참고).
          </p>
        </div>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="mb-3 text-lg font-semibold text-white">AI·규칙 기반 추천 문장</h2>
        {rec[0] ? (
          <p className="whitespace-pre-wrap leading-relaxed text-slate-300">{rec[0].content}</p>
        ) : (
          <p className="text-slate-500">백엔드 연결 후 확인할 수 있습니다.</p>
        )}
      </section>

      <p className="text-center text-sm text-slate-500">
        <Link href={`/category/${cat}`} className="text-sky-400 hover:underline">
          이 직군의 차트·격차 분석 보기 →
        </Link>
      </p>
    </div>
  );
}
