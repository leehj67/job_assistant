"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ResumeAnalysisCharts } from "@/components/ResumeAnalysisCharts";
import { ResumeInsightPanel } from "@/components/ResumeInsightPanel";
import {
  getApplicantPreparation,
  getApplicantProfile,
  getCategories,
  postApplicantJobCoverLetter,
  postApplicantMatchJobs,
  postCollectSuggest,
  postResumePdfAnalyze,
  putApplicantProfile,
  type MatchedJobItem,
  type PreparationInsight,
  type CategoryItem,
  type ResumePdfAnalyzeResult,
  type ResumeSkillItem,
} from "@/lib/api";
import { storeCollectSuggestions } from "@/lib/collectApply";

export function ResumeDashboardPanel() {
  const [dashCats, setDashCats] = useState<CategoryItem[]>([
    { slug: "all", label: "전체 직군" },
    { slug: "data_analyst", label: "데이터 분석가" },
    { slug: "ai_engineer", label: "AI 엔지니어" },
    { slug: "backend_developer", label: "백엔드 개발자" },
  ]);
  const dashSlugs = useMemo(() => new Set(dashCats.map((c) => c.slug)), [dashCats]);
  const [resumeText, setResumeText] = useState("");
  const [careerSummary, setCareerSummary] = useState("");
  const [category, setCategory] = useState("data_analyst");
  const [prepCategory, setPrepCategory] = useState("data_analyst");
  const [saving, setSaving] = useState(false);
  const [matching, setMatching] = useState(false);
  const [prepLoading, setPrepLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState<string | null>(null);
  const [resumeSkills, setResumeSkills] = useState<ResumeSkillItem[]>([]);
  const [matchedJobs, setMatchedJobs] = useState<MatchedJobItem[]>([]);
  const [jobCoverById, setJobCoverById] = useState<
    Record<
      number,
      { loading: boolean; text?: string; err?: string; generated_by?: string; char_count?: number }
    >
  >({});
  const [prep, setPrep] = useState<PreparationInsight | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [applyPdfToProfile, setApplyPdfToProfile] = useState(true);
  const [pdfAnalysis, setPdfAnalysis] = useState<ResumePdfAnalyzeResult | null>(null);
  const pdfInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getApplicantProfile()
      .then((p) => {
        setResumeText(p.resume_text ?? "");
        setCareerSummary(p.career_summary ?? "");
      })
      .catch(() => {
        /* 프로필 없음 등은 무시 */
      });
  }, []);

  useEffect(() => {
    getCategories()
      .then((c) => {
        if (c.length)
          setDashCats([{ slug: "all", label: "전체 직군" }, ...c]);
      })
      .catch(() => {
        /* 기본 목록 유지 */
      });
  }, []);

  useEffect(() => {
    if (dashCats.length > 0 && !dashSlugs.has(category)) {
      setCategory(dashCats[0].slug);
    }
    if (dashCats.length > 0 && !dashSlugs.has(prepCategory)) {
      setPrepCategory(dashCats[0].slug);
    }
  }, [dashCats, dashSlugs, category, prepCategory]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    setSaveOk(null);
    try {
      await putApplicantProfile({
        resume_text: resumeText || null,
        career_summary: careerSummary || null,
        application_prefs: { last_dashboard_category: category },
      });
      setSaveOk("프로필에 저장했습니다.");
    } catch (x) {
      setErr(x instanceof Error ? x.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  }

  async function onMatch() {
    setMatching(true);
    setErr(null);
    setSaveOk(null);
    try {
      const cat = category === "all" ? null : category;
      const r = await postApplicantMatchJobs({
        resume_text: resumeText,
        career_summary: careerSummary,
        category: cat,
        limit: 20,
      });
      setResumeSkills(r.resume_skills);
      setMatchedJobs(r.jobs);
      setJobCoverById({});
    } catch (x) {
      setErr(x instanceof Error ? x.message : "매칭 실패");
    } finally {
      setMatching(false);
    }
  }

  async function onJobCoverLetter(jobId: number) {
    if (!resumeText.trim() && !careerSummary.trim()) {
      setErr("자기소개서 생성: 이력서 본문 또는 경력 요약을 먼저 입력해 주세요.");
      return;
    }
    setErr(null);
    setJobCoverById((m) => ({ ...m, [jobId]: { loading: true } }));
    try {
      const r = await postApplicantJobCoverLetter({
        job_id: jobId,
        resume_text: resumeText,
        career_summary: careerSummary,
      });
      setJobCoverById((m) => ({
        ...m,
        [jobId]: {
          loading: false,
          text: r.text,
          generated_by: r.generated_by,
          char_count: r.char_count,
        },
      }));
    } catch (x) {
      setJobCoverById((m) => ({
        ...m,
        [jobId]: { loading: false, err: x instanceof Error ? x.message : "생성 실패" },
      }));
    }
  }

  async function onPreparation() {
    setPrepLoading(true);
    setErr(null);
    try {
      const cat = prepCategory === "all" ? null : prepCategory;
      const r = await getApplicantPreparation(cat);
      setPrep(r);
    } catch (x) {
      setErr(x instanceof Error ? x.message : "분석 실패");
    } finally {
      setPrepLoading(false);
    }
  }

  async function applyCollectToPanel() {
    setErr(null);
    setSaveOk(null);
    try {
      const s = await postCollectSuggest({
        resume_text: resumeText,
        career_summary: careerSummary,
        analysis_category_hint: category === "all" ? null : category,
      });
      storeCollectSuggestions(s);
      setSaveOk(
        `공고 수집란에 반영: ${s.primary_category_label_ko} · 키워드 ${s.search_keywords.length}개`
      );
      document.getElementById("collect-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (x) {
      setErr(x instanceof Error ? x.message : "수집 추천 반영 실패");
    }
  }

  function reapplyPdfCollectSuggestions() {
    if (!pdfAnalysis?.collect_suggestions) return;
    storeCollectSuggestions(pdfAnalysis.collect_suggestions);
    setSaveOk("PDF 분석 기준으로 수집란을 다시 채웠습니다.");
    document.getElementById("collect-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function onPdfChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setErr("PDF 파일만 업로드할 수 있습니다.");
      return;
    }
    setPdfLoading(true);
    setErr(null);
    setSaveOk(null);
    try {
      const cat = category === "all" ? null : category;
      const r = await postResumePdfAnalyze(file, {
        category: cat,
        applyToProfile: applyPdfToProfile,
      });
      setPdfAnalysis(r);
      setResumeText(r.resume_text);
      setCareerSummary(r.career_summary_suggested);
      setResumeSkills(r.core_skills);
      storeCollectSuggestions(r.collect_suggestions);
      setSaveOk(
        r.profile_updated
          ? "PDF 분석 완료. 프로필 반영 + 상단 공고 수집란에 추천 키워드·직군이 채워졌습니다."
          : "PDF 분석 완료. 상단 공고 수집란에 추천이 반영되었습니다. 필요하면 「프로필에 저장」하세요."
      );
    } catch (x) {
      setErr(x instanceof Error ? x.message : "PDF 분석 실패");
    } finally {
      setPdfLoading(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
      <h2 className="text-lg font-semibold text-white">내 이력서 · 맞춤 공고 · 준비 인사이트</h2>
      <p className="mt-1 text-sm text-slate-400">
        이력서와 경력 요약에서 규칙 기반으로 키워드를 뽑고, 수집된 공고의 스킬·자격 메타와 겹치는 정도로
        적합도를 매깁니다.         PDF는 텍스트 레이어가 있어야 추출됩니다(스캔본은 OCR 후 사용). 로컬(
        <code className="rounded bg-slate-900 px-1">localhost</code>)에서는 업로드가 백엔드(
        <code className="rounded bg-slate-900 px-1">127.0.0.1:8000</code>)로 직접 가서 Next 프록시
        용량 이슈를 피합니다. 원격 배포 시에는{" "}
        <code className="rounded bg-slate-900 px-1">NEXT_PUBLIC_API_URL</code>을 설정하세요.
      </p>
      <p className="mt-2 text-xs text-slate-500">
        <Link href="/consultant" className="text-sky-400 hover:underline">
          컨설턴트 보드
        </Link>
        에서 저장한 프로필을 학생으로 가져오거나, 학생별 일정·월간 목표를 관리할 수 있습니다.
      </p>

      <div className="mt-4 flex flex-col gap-3 rounded-lg border border-slate-800 bg-slate-950/50 p-4 sm:flex-row sm:flex-wrap sm:items-center">
        <input
          ref={pdfInputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={onPdfChange}
        />
        <button
          type="button"
          disabled={pdfLoading}
          onClick={() => pdfInputRef.current?.click()}
          className="rounded-lg border border-emerald-800 bg-emerald-950/40 px-4 py-2 text-sm text-emerald-200 hover:bg-emerald-900/30 disabled:opacity-50"
        >
          {pdfLoading ? "PDF 분석 중…" : "PDF 업로드 · 분석"}
        </button>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
          <input
            type="checkbox"
            checked={applyPdfToProfile}
            onChange={(e) => setApplyPdfToProfile(e.target.checked)}
            className="rounded border-slate-600"
          />
          분석 후 프로필에 이력서 본문·경력 요약·연차(추정) 자동 반영
        </label>
        <p className="text-xs text-slate-500">
          비교 직군은 아래 「추천 직군」과 동일합니다. 먼저 직군을 고른 뒤 PDF를 올리면 그 범위 공고와
          맞춥니다.
        </p>
      </div>

      <form onSubmit={onSave} className="mt-4 space-y-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">이력서 본문 (텍스트)</label>
          <textarea
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            rows={8}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-sky-600 focus:outline-none"
            placeholder="경력, 프로젝트, 사용 기술 스택을 붙여 넣으세요. (Python, SQL, Tableau …)"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-400">경력 요약 (선택)</label>
          <textarea
            value={careerSummary}
            onChange={(e) => setCareerSummary(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-sky-600 focus:outline-none"
            placeholder="3~5줄 요약"
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm text-slate-100 hover:border-slate-500 disabled:opacity-50"
          >
            {saving ? "저장 중…" : "프로필에 저장"}
          </button>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">추천 직군</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-200"
            >
              {dashCats.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label} (추천 범위)
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={onMatch}
              disabled={matching}
              className="rounded-lg border border-sky-700 bg-sky-950/60 px-4 py-2 text-sm text-sky-200 hover:bg-sky-900/50 disabled:opacity-50"
            >
              {matching ? "분석 중…" : "키워드 추출 · 적합 공고 추천"}
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-800/80 pt-3">
          <button
            type="button"
            onClick={applyCollectToPanel}
            className="rounded-lg border border-teal-800 bg-teal-950/40 px-3 py-2 text-sm text-teal-200 hover:bg-teal-900/30"
          >
            공고 수집란에 키워드·직군 반영
          </button>
          <span className="text-xs text-slate-500">
            위 이력서·경력·「추천 직군」선택을 반영해 상단 수집 폼을 채웁니다.
          </span>
        </div>
      </form>

      <ResumeInsightPanel
        resumeText={resumeText}
        careerSummary={careerSummary}
        category={category}
        onCollectApplied={(detail) => {
          setErr(null);
          setSaveOk(`시장 인사이트 기준 공고 수집란 반영: ${detail}`);
        }}
      />

      {saveOk && <p className="mt-2 text-sm text-emerald-400">{saveOk}</p>}
      {err && (
        <p className="mt-2 rounded border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {err}
        </p>
      )}

      {pdfAnalysis && (
        <div className="mt-4 space-y-3 rounded-lg border border-slate-800 bg-slate-950/40 p-4 text-sm">
          <p className="text-slate-400">
            추출 글자 수 <span className="text-slate-200">{pdfAnalysis.extracted_char_count}</span>
            {pdfAnalysis.text_truncated && (
              <span className="text-amber-400">
                {" "}
                · 응답 JSON의 이력서 본문만 잘렸습니다.
                {pdfAnalysis.profile_updated
                  ? " 전체는 프로필에 저장되었습니다."
                  : " 「프로필에 저장」을 누르면 전체가 서버에 반영됩니다."}
              </span>
            )}
          </p>
          {pdfAnalysis.career_years_estimate != null && (
            <p className="text-slate-400">
              경력 연차(추정):{" "}
              <span className="text-slate-200">{pdfAnalysis.career_years_estimate}년</span>
            </p>
          )}
          {pdfAnalysis.applicable_areas.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-500">지원 가능 영역(추정)</p>
              <ul className="mt-1 flex flex-wrap gap-2">
                {pdfAnalysis.applicable_areas.map((a) => (
                  <li
                    key={a}
                    className="rounded-full border border-sky-900/60 bg-sky-950/40 px-3 py-0.5 text-xs text-sky-200"
                  >
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {pdfAnalysis.summary_paragraph && (
            <div>
              <p className="text-xs font-medium text-slate-500">요약 문단</p>
              <p className="mt-1 leading-relaxed text-slate-300">{pdfAnalysis.summary_paragraph}</p>
            </div>
          )}
          {pdfAnalysis.strengths.length > 0 && (
            <div>
              <p className="text-xs font-medium text-emerald-500/90">강점 (공고 상위 스킬 대비)</p>
              <ul className="mt-1 list-inside list-disc text-slate-400">
                {pdfAnalysis.strengths.slice(0, 8).map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {pdfAnalysis.weaknesses.length > 0 && (
            <div>
              <p className="text-xs font-medium text-amber-500/90">보완점</p>
              <ul className="mt-1 list-inside list-disc text-slate-400">
                {pdfAnalysis.weaknesses.slice(0, 8).map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {pdfAnalysis.preparation_notes.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-500">준비 사항</p>
              <ul className="mt-1 list-inside list-disc text-slate-400">
                {pdfAnalysis.preparation_notes.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {pdfAnalysis.collect_suggestions && (
            <div className="rounded-lg border border-teal-900/50 bg-teal-950/25 p-3">
              <p className="text-xs font-medium text-teal-200/90">공고 수집 추천</p>
              <p className="mt-1 text-sm text-slate-300">
                1순위 직군(저장용):{" "}
                <strong className="text-slate-100">
                  {pdfAnalysis.collect_suggestions.primary_category_label_ko}
                </strong>
              </p>
              <p className="mt-1 text-xs text-slate-500">
                검색 키워드: {pdfAnalysis.collect_suggestions.search_keywords.join(", ")}
              </p>
              {pdfAnalysis.collect_suggestions.role_expansion_notes.length > 0 && (
                <ul className="mt-2 list-inside list-disc text-xs text-amber-200/85">
                  {pdfAnalysis.collect_suggestions.role_expansion_notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                onClick={reapplyPdfCollectSuggestions}
                className="mt-2 rounded border border-teal-700 px-2 py-1 text-xs text-teal-200 hover:bg-teal-900/30"
              >
                수집란에 다시 반영 · 스크롤
              </button>
            </div>
          )}
          <ResumeAnalysisCharts charts={pdfAnalysis.charts} />
        </div>
      )}

      {(resumeSkills.length > 0 || matchedJobs.length > 0) && (
        <div className="mt-6 space-y-4 border-t border-slate-800 pt-6">
          {resumeSkills.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-200">이력서에서 추출된 키워드</h3>
              <ul className="mt-2 flex flex-wrap gap-2">
                {resumeSkills.map((s) => (
                  <li
                    key={s.normalized}
                    className="rounded-full border border-slate-600 bg-slate-800/80 px-3 py-1 text-xs text-slate-200"
                  >
                    {s.normalized}{" "}
                    <span className="text-slate-500">({s.skill_group})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {matchedJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-200">적합도 순 공고</h3>
              <p className="mt-1 text-xs text-slate-500">
                공고에 추출된 스킬·제목·자격요건 문구와의 겹침을 반영한 데모 점수입니다. 자격요건은
                공고 메타(파싱된 필수 항목)와 이력서·경력 합본을 비교합니다. 각 공고의「자기소개서
                생성」은 클릭할 때만 LLM이 호출되어 불필요한 토큰 사용을 줄입니다(약 1000자 분량).
              </p>
              <ul className="mt-3 space-y-2">
                {matchedJobs.map((j) => (
                  <li
                    key={j.id}
                    className="flex flex-col gap-2 rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2"
                  >
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <Link
                        href={`/job/${j.id}`}
                        className="font-medium text-sky-300 hover:text-sky-200"
                      >
                        {j.title}
                      </Link>
                      <p className="text-xs text-slate-500">
                        {j.company} · {j.category} · 스킬 {j.job_skill_count}개 추출
                      </p>
                      {j.matched_skills.length > 0 && (
                        <p className="mt-1 text-xs text-slate-400">
                          일치: {j.matched_skills.join(", ")}
                        </p>
                      )}
                      {(j.requirements_total ?? 0) === 0 ? (
                        <p className="mt-1 text-xs text-slate-600">
                          자격요건 메타 없음 — 상세 수집·파싱된 공고에서 비교가 가능합니다.
                        </p>
                      ) : (j.requirements_mismatch ?? []).length > 0 ? (
                        <div className="mt-2 rounded border border-amber-900/50 bg-amber-950/25 px-2 py-1.5">
                          <p className="text-xs font-medium text-amber-200/90">
                            이력서와 맞지 않는 자격요건 (
                            {(j.requirements_mismatch ?? []).length}/{j.requirements_total})
                          </p>
                          <ul className="mt-1 list-inside list-disc text-xs text-amber-100/85">
                            {(j.requirements_mismatch ?? []).map((line, idx) => (
                              <li key={idx} className="break-words">
                                {line}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-emerald-500/90">
                          파싱된 자격요건 {j.requirements_total ?? 0}줄 — 이력서 키워드와 겹침으로 표시됨
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2 sm:flex-row sm:items-center">
                      <span className="rounded bg-slate-800 px-2 py-1 text-xs text-amber-200">
                        점수 {j.match_score.toFixed(1)}
                      </span>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {j.source_url && (
                          <a
                            href={j.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-slate-400 underline hover:text-slate-200"
                          >
                            원문
                          </a>
                        )}
                        <button
                          type="button"
                          disabled={
                            Boolean(jobCoverById[j.id]?.loading) ||
                            (!resumeText.trim() && !careerSummary.trim())
                          }
                          onClick={() => onJobCoverLetter(j.id)}
                          className="rounded border border-violet-700/80 bg-violet-950/40 px-2 py-1 text-xs text-violet-200 hover:bg-violet-900/35 disabled:opacity-50"
                          title="이 공고에 맞춘 자기소개서 초안을 LLM으로 생성합니다(클릭 시에만 호출)"
                        >
                          {jobCoverById[j.id]?.loading ? "생성 중…" : "자기소개서 생성"}
                        </button>
                      </div>
                    </div>
                    </div>
                    {(jobCoverById[j.id]?.text || jobCoverById[j.id]?.err) && (
                      <div className="w-full border-t border-slate-800/90 pt-3">
                        {jobCoverById[j.id]?.err ? (
                          <p className="text-xs text-rose-400">{jobCoverById[j.id]?.err}</p>
                        ) : (
                          <>
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-xs text-slate-500">
                                {jobCoverById[j.id]?.generated_by === "llm"
                                  ? "LLM 생성 본문 (이력서·경력에 근거한 표현만 유지하세요)"
                                  : "참고용 뼈대 (LLM 미연결 또는 응답 실패)"}{" "}
                                · {jobCoverById[j.id]?.char_count ?? jobCoverById[j.id]?.text?.length}
                                자
                              </p>
                              <button
                                type="button"
                                onClick={() => {
                                  const t = jobCoverById[j.id]?.text;
                                  if (t) void navigator.clipboard.writeText(t);
                                }}
                                className="rounded border border-slate-600 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-slate-800"
                              >
                                복사
                              </button>
                            </div>
                            <div className="mt-2 max-h-72 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/80 p-3 text-sm leading-relaxed text-slate-200 whitespace-pre-wrap">
                              {jobCoverById[j.id]?.text}
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="mt-8 border-t border-slate-800 pt-6">
        <h3 className="text-sm font-semibold text-slate-200">업계 요구 · 준비 사항</h3>
        <p className="mt-1 text-xs text-slate-500">
          저장된 이력서·경력 요약과 비교합니다. 먼저 위에서 프로필에 저장한 뒤 실행하는 것을 권장합니다.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            value={prepCategory}
            onChange={(e) => setPrepCategory(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-200"
          >
            {dashCats.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={onPreparation}
            disabled={prepLoading}
            className="rounded-lg border border-violet-700 bg-violet-950/50 px-4 py-2 text-sm text-violet-200 hover:bg-violet-900/40 disabled:opacity-50"
          >
            {prepLoading ? "분석 중…" : "요구 스킬 · 갭 분석"}
          </button>
        </div>

        {prep && (
          <div className="mt-4 space-y-4 text-sm">
            {prep.industry_top_skills.length > 0 && (
              <div>
                <p className="font-medium text-slate-300">최근 공고에서 많이 등장하는 스킬 (상위)</p>
                <ul className="mt-2 grid gap-1 sm:grid-cols-2">
                  {prep.industry_top_skills.slice(0, 12).map((s) => (
                    <li key={s.normalized_skill} className="text-slate-400">
                      <span className="text-slate-200">{s.normalized_skill}</span> — 공고{" "}
                      {s.job_count}건
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {prep.gap_skills.length > 0 && (
              <div>
                <p className="font-medium text-amber-200/90">이력서 대비 부족하기 쉬운 요구 스킬</p>
                <p className="mt-1 text-slate-400">{prep.gap_skills.join(", ")}</p>
              </div>
            )}
            {prep.action_items.length > 0 && (
              <div>
                <p className="font-medium text-slate-300">준비·보완 제안</p>
                <ul className="mt-2 list-inside list-disc space-y-1 text-slate-400">
                  {prep.action_items.map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
              </div>
            )}
            {prep.industry_top_skills.length === 0 && (
              <p className="text-slate-500">
                해당 직군에 수집된 공고가 없거나 스킬이 아직 추출되지 않았습니다. 공고 수집을 먼저
                실행해 보세요.
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
