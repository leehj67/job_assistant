import Link from "next/link";
import { getCategories, getRecommendations, getGap } from "@/lib/api";

export default async function JobseekerPage({
  searchParams,
}: {
  searchParams: Promise<{ cat?: string }>;
}) {
  const { cat = "data_analyst" } = await searchParams;
  const categories = await getCategories().catch(() => [] as { slug: string; label: string }[]);
  const rec = await getRecommendations(cat, "jobseeker").catch(() => []);
  const gap = await getGap(cat).catch(() => []);

  const over = gap.filter((g) => g.gap_type === "oversaturated");
  const opp = gap.filter((g) => g.gap_type === "opportunity");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">취업준비생용 인사이트</h1>
        <p className="mt-1 text-slate-400">
          우선 학습 스킬, 과포화 경고, 유망 직무 방향을 데모 데이터로 정리했습니다.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {categories.map((c) => (
          <Link
            key={c.slug}
            href={`/jobseeker?cat=${c.slug}`}
            className={`rounded-lg border px-3 py-1 text-sm ${
              cat === c.slug
                ? "border-sky-500 bg-sky-950/50 text-sky-200"
                : "border-slate-700 text-slate-300 hover:border-slate-500"
            }`}
          >
            {c.label}
          </Link>
        ))}
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-sky-300">우선 학습</h2>
          <p className="mt-2 text-sm text-slate-300">
            공고에 자주 등장하는 스킬을 먼저 — 상세는 직군 페이지 차트 참고.
          </p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-rose-300">과포화 경고</h2>
          <p className="mt-2 text-sm text-slate-300">
            {over.slice(0, 6).map((x) => x.keyword).join(", ") || "—"}
          </p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <h2 className="text-sm font-semibold text-emerald-300">유망 방향</h2>
          <p className="mt-2 text-sm text-slate-300">
            {opp.slice(0, 6).map((x) => x.keyword).join(", ") || "—"}
          </p>
        </div>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="mb-3 text-lg font-semibold text-white">맞춤 전략 문장</h2>
        {rec[0] ? (
          <p className="whitespace-pre-wrap leading-relaxed text-slate-300">{rec[0].content}</p>
        ) : (
          <p className="text-slate-500">백엔드 연결 후 확인할 수 있습니다.</p>
        )}
      </section>

      <p className="text-center text-sm text-slate-500">
        <Link href={`/category/${cat}`} className="text-sky-400 hover:underline">
          차트와 수요·관심 비교 보기 →
        </Link>
      </p>
    </div>
  );
}
