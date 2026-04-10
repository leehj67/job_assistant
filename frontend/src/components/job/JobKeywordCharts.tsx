"use client";

import type { KeywordAnalysis } from "@/lib/api";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#f472b6", "#fb923c", "#94a3b8"];

const CAT_KO: Record<string, string> = {
  data_analyst: "데이터 분석가",
  ai_engineer: "AI 엔지니어",
  backend_developer: "백엔드 개발자",
};

function sectionKo(s: string | null | undefined) {
  if (!s) return "";
  if (s === "required") return "필수";
  if (s === "preferred") return "우대";
  if (s === "work") return "업무";
  if (s === "unknown") return "미분류";
  return s;
}

function chartTooltipStyle() {
  return {
    contentStyle: { background: "#0f172a", border: "1px solid #334155" },
    labelStyle: { color: "#e2e8f0" },
  };
}

export function JobKeywordCharts({ data }: { data: KeywordAnalysis }) {
  const fs = data.form_summary;
  const career = fs.career as { type?: string; min_years?: number | null } | null;
  const careerLabel =
    career?.type === "unknown" || !career?.type
      ? "—"
      : career.type === "경력" && career.min_years != null
        ? `경력 ${career.min_years}년 이상`
        : career.type;

  const techData = data.technical_terms.slice(0, 16).map((t) => ({
    name: t.term.length > 22 ? `${t.term.slice(0, 20)}…` : t.term,
    fullTerm: t.term,
    count: t.count,
    group: t.group_label_ko,
    section: t.section,
    normalized: t.normalized,
  }));

  const pieData = data.group_distribution.map((g) => ({
    name: g.label_ko,
    value: g.count,
  }));

  const wordData = data.word_frequency.slice(0, 22).map((w) => ({
    name: w.token.length > 14 ? `${w.token.slice(0, 12)}…` : w.token,
    full: w.token,
    count: w.count,
  }));

  return (
    <div className="space-y-10">
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <p className="text-xs font-medium text-slate-500">업무·근무 위치</p>
          <p className="mt-1 text-sm text-slate-100">{fs.work_location ?? "—"}</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <p className="text-xs font-medium text-slate-500">연봉·급여</p>
          <p className="mt-1 text-sm text-slate-100">{fs.salary ?? "—"}</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <p className="text-xs font-medium text-slate-500">경력 조건</p>
          <p className="mt-1 text-sm text-slate-100">{careerLabel}</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <p className="text-xs font-medium text-slate-500">본문 섹션(줄 수)</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-300">
            담당 {fs.responsibilities_lines} · 요구 {fs.requirements_lines} · 우대{" "}
            {fs.preferred_lines}
          </p>
        </div>
      </section>

      {data.pipeline?.stage1 && (
        <section className="space-y-3 rounded-xl border border-emerald-900/50 bg-emerald-950/20 p-4">
          <h2 className="text-lg font-semibold text-emerald-200">1단계: RAKE · YAKE · Kiwi</h2>
          <p className="text-xs text-slate-400">
            광범위 후보(노이즈 허용) — 총 {data.pipeline.stage1.counts?.combined ?? 0}개 후보
          </p>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded bg-slate-800 px-2 py-1 text-slate-300">
              RAKE {data.pipeline.stage1.counts?.rake ?? 0}
            </span>
            <span className="rounded bg-slate-800 px-2 py-1 text-slate-300">
              YAKE {data.pipeline.stage1.counts?.yake ?? 0}
            </span>
            <span className="rounded bg-slate-800 px-2 py-1 text-slate-300">
              Kiwi {data.pipeline.stage1.counts?.kiwi ?? 0}
            </span>
            <span className="rounded bg-slate-800 px-2 py-1 text-slate-300">
              KoBERT토큰 {data.pipeline.stage1.counts?.kobert ?? 0}
            </span>
          </div>
          <details className="text-sm">
            <summary className="cursor-pointer text-slate-400">통합 후보 미리보기</summary>
            <p className="mt-2 max-h-40 overflow-y-auto rounded border border-slate-800 p-2 font-mono text-[11px] leading-relaxed text-slate-500">
              {(data.pipeline.stage1.combined_candidates ?? []).slice(0, 150).join(" · ")}
            </p>
          </details>
        </section>
      )}

      {data.pipeline?.stage2 && (
        <section className="rounded-xl border border-sky-900/50 bg-sky-950/20 p-4">
          <h2 className="text-lg font-semibold text-sky-200">2단계: LLM 정제·정규화·섹션</h2>
          <p className="mt-1 text-xs text-slate-400">
            OpenAI 키: {data.pipeline.stage2.openai_configured ? "있음" : "없음"} · Ollama:{" "}
            {data.pipeline.stage2.ollama_reachable ? "응답" : "미응답"} (
            <code className="text-slate-500">ollama serve</code> · 모델 pull 필요)
          </p>
          {data.pipeline.stage2.error && (
            <p className="mt-2 rounded border border-amber-700/50 bg-amber-950/40 px-3 py-2 text-xs text-amber-200">
              {data.pipeline.stage2.error}
            </p>
          )}
        </section>
      )}

      {(data.soft_skills ?? []).length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-white">소프트스킬 (LLM 분리)</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {(data.soft_skills ?? []).map((s, i) => (
              <span
                key={i}
                className="rounded-full border border-rose-800/60 bg-rose-950/40 px-3 py-1 text-xs text-rose-100"
              >
                {s.phrase}
                {s.section ? ` · ${sectionKo(s.section)}` : ""}
              </span>
            ))}
          </div>
        </section>
      )}

      <p className="text-xs text-slate-500">
        분석 원문 길이 약 {data.analyzed_char_length}자 (제목·회사·메타 본문 합산). 상세 수집을 켜면
        키워드가 풍부해집니다.
      </p>

      <section className="rounded-xl border border-slate-800 bg-slate-900/30 p-4">
        <h2 className="text-lg font-semibold text-white">기술·도구 키워드 (분류별 비중)</h2>
        <p className="mt-1 text-sm text-slate-400">
          {data.pipeline?.stage2?.llm
            ? "2단계 LLM 기준 카테고리(language · framework · tool · domain) 비중입니다."
            : "LLM 미적용 시 사전 규칙 기반 그룹으로 표시됩니다."}
        </p>
        <div className="mt-4 h-80 w-full min-h-[16rem] min-w-0">
          {pieData.length === 0 ? (
            <p className="py-12 text-center text-slate-500">매칭된 기술 키워드가 없습니다.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={110}
                  label={false}
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip {...chartTooltipStyle()} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/30 p-4">
        <h2 className="text-lg font-semibold text-white">기술 키워드 (상위 · 막대)</h2>
        <p className="mt-1 text-xs text-slate-500">
          마우스 오버: 섹션(필수/우대/업무), 정규화 ID
        </p>
        <div className="mt-4 h-[28rem] w-full min-w-0">
          {techData.length === 0 ? (
            <p className="py-8 text-center text-slate-500">데이터 없음</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={techData}
                margin={{ top: 4, right: 12, left: 4, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={100}
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const p = payload[0].payload as {
                      fullTerm: string;
                      count: number;
                      group: string;
                      name: string;
                      section?: string | null;
                      normalized?: string | null;
                    };
                    return (
                      <div className="rounded border border-slate-600 bg-slate-900 px-3 py-2 text-xs shadow-lg">
                        <div className="font-medium text-slate-100">{p.fullTerm}</div>
                        {p.normalized && (
                          <div className="text-slate-500">norm: {p.normalized}</div>
                        )}
                        <div className="text-sky-300">가중/출현 {p.count}</div>
                        <div className="text-slate-500">{p.group}</div>
                        {p.section && (
                          <div className="text-emerald-400/90">섹션: {sectionKo(p.section)}</div>
                        )}
                      </div>
                    );
                  }}
                />
                <Bar dataKey="count" fill="#38bdf8" radius={[0, 4, 4, 0]} name="출현 수" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/30 p-4">
        <h2 className="text-lg font-semibold text-white">일반 단어 빈도 (형태소 단순 분리)</h2>
        <p className="mt-1 text-sm text-slate-400">
          기술 사전과 겹치지 않는 토큰 위주입니다. 한글·영문 짧은 단위로 집계됩니다.
        </p>
        <div className="mt-4 h-96 w-full min-w-0">
          {wordData.length === 0 ? (
            <p className="py-8 text-center text-slate-500">토큰이 없습니다.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={wordData} margin={{ top: 8, right: 8, left: 0, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#94a3b8", fontSize: 10 }}
                  interval={0}
                  angle={-35}
                  textAnchor="end"
                  height={70}
                />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <Tooltip
                  {...chartTooltipStyle()}
                  labelFormatter={(l) =>
                    wordData.find((w) => w.name === l)?.full ?? l
                  }
                />
                <Bar dataKey="count" fill="#a78bfa" radius={[4, 4, 0, 0]} name="빈도" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      <p className="text-center text-xs text-slate-600">
        직군: {CAT_KO[data.category] ?? data.category}
      </p>
    </div>
  );
}
