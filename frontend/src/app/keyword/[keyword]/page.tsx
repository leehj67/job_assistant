import Link from "next/link";
import { notFound } from "next/navigation";
import { getJobsByKeyword } from "@/lib/api";

type Q = {
  region?: string;
  career?: string;
  sort?: string;
};

function isSeoul(loc: string | null): boolean {
  if (!loc) return false;
  return loc.includes("서울");
}

function matchCareer(label: string | null, career: string): boolean {
  const v = (label || "").trim();
  if (career === "all") return true;
  if (career === "new") return v.includes("신입");
  if (career === "agnostic") return v.includes("무관");
  if (career === "experienced") return v.includes("경력");
  return true;
}

export default async function KeywordJobsPage({
  params,
  searchParams,
}: {
  params: Promise<{ keyword: string }>;
  searchParams: Promise<Q>;
}) {
  const { keyword } = await params;
  const q = await searchParams;
  const decoded = decodeURIComponent(keyword);
  const jobs = await getJobsByKeyword(decoded, 300).catch(() => null);
  if (!jobs) notFound();

  const region = q.region ?? "all";
  const career = q.career ?? "all";
  const sort = q.sort ?? "career_loc";

  const filtered = jobs.filter((j) => {
    const regionOk =
      region === "all" ||
      (region === "seoul" && isSeoul(j.work_location)) ||
      (region === "other" && !isSeoul(j.work_location));
    const careerOk = matchCareer(j.career_label, career);
    return regionOk && careerOk;
  });

  const sorted = [...filtered].sort((a, b) => {
    if (sort === "location") {
      return (a.work_location || "미정").localeCompare(b.work_location || "미정", "ko");
    }
    if (sort === "career") {
      return (a.career_label || "미정").localeCompare(b.career_label || "미정", "ko");
    }
    return (
      (a.career_label || "미정").localeCompare(b.career_label || "미정", "ko") ||
      (a.work_location || "미정").localeCompare(b.work_location || "미정", "ko") ||
      b.id - a.id
    );
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <nav className="text-sm text-slate-500">
        <Link href="/" className="text-sky-400 hover:underline">
          대시보드
        </Link>
        <span className="mx-2">/</span>
        <span className="text-slate-300">키워드</span>
      </nav>

      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-white md:text-3xl">
          키워드: <span className="text-sky-300">{decoded}</span>
        </h1>
        <p className="text-sm text-slate-400">
          연차 → 기업 위치 기준 정렬. 각 공고의 원본 링크/키워드 분석 페이지로 이동할 수 있습니다.
        </p>
      </header>

      <form className="grid gap-3 rounded-xl border border-slate-800 bg-slate-900/40 p-4 sm:grid-cols-3">
        <input type="hidden" name="q" value={decoded} />
        <label className="text-sm text-slate-300">
          지역
          <select
            name="region"
            defaultValue={region}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
          >
            <option value="all">전체</option>
            <option value="seoul">서울</option>
            <option value="other">그외</option>
          </select>
        </label>
        <label className="text-sm text-slate-300">
          연차
          <select
            name="career"
            defaultValue={career}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
          >
            <option value="all">전체</option>
            <option value="new">신입</option>
            <option value="agnostic">경력무관</option>
            <option value="experienced">경력</option>
          </select>
        </label>
        <label className="text-sm text-slate-300">
          정렬
          <select
            name="sort"
            defaultValue={sort}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
          >
            <option value="career_loc">연차 → 위치</option>
            <option value="career">연차</option>
            <option value="location">위치</option>
          </select>
        </label>
        <button
          type="submit"
          className="sm:col-span-3 w-fit rounded bg-sky-600 px-3 py-1.5 text-sm text-white hover:bg-sky-500"
        >
          적용
        </button>
      </form>

      {sorted.length === 0 ? (
        <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-500">
          조건에 맞는 공고가 없습니다.
        </p>
      ) : (
        <ul className="space-y-3">
          {sorted.map((j) => (
            <li key={j.id} className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                  {j.source}
                </span>
                <h2 className="text-base font-semibold text-slate-100">{j.title}</h2>
              </div>
              <p className="mt-1 text-sm text-slate-400">
                {j.company} · 연차 {j.career_label ?? "미정"} · 위치 {j.work_location ?? "미정"}
              </p>
              <div className="mt-3 flex flex-wrap gap-3 text-sm">
                <Link href={`/job/${j.id}`} className="text-emerald-400 hover:underline">
                  키워드 분석 보기
                </Link>
                {j.source_url ? (
                  <a
                    href={j.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all text-sky-400 hover:underline"
                  >
                    원본 링크 열기
                  </a>
                ) : (
                  <span className="text-slate-600">원본 링크 없음</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
