import Link from "next/link";
import { notFound } from "next/navigation";
import { JobKeywordCharts } from "@/components/job/JobKeywordCharts";
import { getJobKeywordAnalysis } from "@/lib/api";

export default async function JobKeywordPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const jid = Number(id);
  if (!Number.isFinite(jid) || jid < 1) {
    notFound();
  }

  let data = null;
  try {
    data = await getJobKeywordAnalysis(jid);
  } catch {
    notFound();
  }

  if (!data) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4 py-8">
      <nav className="text-sm text-slate-500">
        <Link href="/" className="text-sky-400 hover:underline">
          대시보드
        </Link>
        <span className="mx-2">/</span>
        <span className="text-slate-300">공고 키워드 분석</span>
      </nav>

      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-white md:text-3xl">{data.title}</h1>
        <p className="text-slate-400">
          {data.company} · <span className="text-slate-500">{data.category}</span>
        </p>
      </header>

      <JobKeywordCharts data={data} />
    </div>
  );
}
