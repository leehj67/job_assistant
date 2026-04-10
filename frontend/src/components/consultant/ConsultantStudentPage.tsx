"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  deleteConsultantEvent,
  deleteConsultantStudent,
  deleteConsultantTargetCompany,
  getConsultantCategories,
  getConsultantStudentDetail,
  patchConsultantStudent,
  postConsultantTargetCompany,
  consultantImportLlmHint,
  postImportFromApplicantProfile,
  putConsultantMonthlyGoal,
  type ConsultantCategoryItem,
  type ConsultantStudentDetail,
} from "@/lib/api";

const EVENT_TYPE_KO: Record<string, string> = {
  exam: "시험",
  application_deadline: "지원 마감",
  interview: "면접",
  other: "기타",
};

export function ConsultantStudentPage({ studentId }: { studentId: number }) {
  const router = useRouter();
  const [data, setData] = useState<ConsultantStudentDetail | null>(null);
  const [categories, setCategories] = useState<ConsultantCategoryItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savedOk, setSavedOk] = useState<string | null>(null);
  /** 가져오기 시 LLM 미연결·JSON 실패 등 (저장 성공과 별도 안내) */
  const [importLlmWarn, setImportLlmWarn] = useState<string | null>(null);
  const [importProfileBusy, setImportProfileBusy] = useState(false);
  /** 서버에서 다시 받은 값으로 defaultValue 폼을 동기화하기 위해 load 성공 시마다 증가 */
  const [dataRevision, setDataRevision] = useState(0);

  const [coName, setCoName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const d = await getConsultantStudentDetail(studentId);
      setData(d);
      setDataRevision((n) => n + 1);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "불러오기 실패");
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    getConsultantCategories()
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    if (!data) return;
    const form = e.target as HTMLFormElement;
    const fd = new FormData(form);
    setErr(null);
    setSavedOk(null);
    setImportLlmWarn(null);
    try {
      await patchConsultantStudent(studentId, {
        display_name: String(fd.get("display_name") || "").trim(),
        email: String(fd.get("email") || "") || null,
        phone: String(fd.get("phone") || "") || null,
        school: String(fd.get("school") || "") || null,
        memo: String(fd.get("memo") || "") || null,
        resume_text: String(fd.get("resume_text") || "") || null,
        career_summary: String(fd.get("career_summary") || "") || null,
        target_category: String(fd.get("target_category") || "data_analyst"),
        final_goal_progress: Number(fd.get("final_goal_progress") ?? 0),
      });
      setSavedOk("저장했습니다.");
      await load();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "저장 실패");
    }
  }

  async function saveMonthGoal(e: React.FormEvent) {
    e.preventDefault();
    if (!data) return;
    const form = e.target as HTMLFormElement;
    const fd = new FormData(form);
    const ym = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`;
    setErr(null);
    setSavedOk(null);
    setImportLlmWarn(null);
    try {
      await putConsultantMonthlyGoal(studentId, ym, {
        certifications: String(fd.get("certifications") || ""),
        competencies: String(fd.get("competencies") || ""),
        application_areas: String(fd.get("application_areas") || ""),
      });
      setSavedOk("이번 달 목표를 저장했습니다.");
      await load();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "목표 저장 실패");
    }
  }

  async function addCompany(e: React.FormEvent) {
    e.preventDefault();
    if (!coName.trim()) return;
    setErr(null);
    try {
      await postConsultantTargetCompany(studentId, { company_name: coName.trim() });
      setCoName("");
      await load();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "추가 실패");
    }
  }

  async function removeCompany(id: number) {
    if (!confirm("이 희망 기업을 삭제할까요?")) return;
    try {
      await deleteConsultantTargetCompany(id);
      await load();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "삭제 실패");
    }
  }

  async function removeEvent(id: number) {
    if (!confirm("일정을 삭제할까요?")) return;
    try {
      await deleteConsultantEvent(id);
      await load();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "삭제 실패");
    }
  }

  async function importDashboardProfile() {
    setErr(null);
    setSavedOk(null);
    setImportLlmWarn(null);
    setImportProfileBusy(true);
    try {
      const { importLlmStatus } = await postImportFromApplicantProfile({ student_id: studentId });
      const llmHint = consultantImportLlmHint(importLlmStatus);
      setSavedOk("대시보드 프로필을 이 학생에 반영했습니다.");
      setImportLlmWarn(llmHint);
      await load();
    } catch (x) {
      const raw = x instanceof Error ? x.message : "가져오기 실패";
      setErr(`${raw} — 이력서 대시보드에서 「프로필에 저장」 여부와 백엔드·Ollama 연결을 확인하세요.`);
    } finally {
      setImportProfileBusy(false);
    }
  }

  async function removeStudent() {
    if (!confirm("이 학생을 삭제할까요? 관련 일정·목표·희망기업이 모두 삭제됩니다.")) return;
    setErr(null);
    try {
      await deleteConsultantStudent(studentId);
      router.push("/consultant");
    } catch (x) {
      setErr(x instanceof Error ? x.message : "삭제 실패");
    }
  }

  if (loading && !data) {
    return <p className="text-slate-500">불러오는 중…</p>;
  }
  if (!data) {
    return (
      <p className="text-red-300">
        {err ?? "데이터가 없습니다."}{" "}
        <Link href="/consultant" className="text-sky-400 underline">
          보드로
        </Link>
      </p>
    );
  }

  const s = data.student;
  const ym = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`;
  const mg = data.current_month_goal;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link href="/consultant" className="text-sky-400 hover:underline">
              ← 컨설턴트 보드
            </Link>
            <Link href="/" className="text-slate-400 hover:text-slate-200 hover:underline">
              이력서 대시보드
            </Link>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-white">{s.display_name}</h1>
          <p className="text-sm text-slate-500">
            학생 ID {s.id} · 타깃 직군 {categories.find((c) => c.slug === s.target_category)?.label ?? s.target_category}
          </p>
        </div>
        <button
          type="button"
          onClick={importDashboardProfile}
          disabled={importProfileBusy}
          className="rounded-lg border border-violet-800 bg-violet-950/40 px-4 py-2 text-sm text-violet-200 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {importProfileBusy ? "가져오는 중…" : "대시보드 프로필 가져와서 덮어쓰기"}
        </button>
      </div>

      {importProfileBusy && (
        <div
          role="status"
          aria-live="polite"
          className="rounded-lg border border-sky-800 bg-sky-950/50 px-4 py-3 text-sm text-sky-100"
        >
          <span
            className="mr-2 inline-block size-4 animate-spin rounded-full border-2 border-sky-400 border-t-transparent align-[-3px]"
            aria-hidden
          />
          대시보드 프로필을 불러와 덮어쓰는 중입니다. AI 분석에는 30초~수 분 걸릴 수 있습니다.
        </div>
      )}

      {err && (
        <p className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-2 text-sm text-red-200">{err}</p>
      )}
      {savedOk && <p className="text-sm text-emerald-400">{savedOk}</p>}
      {importLlmWarn && (
        <p className="text-sm text-amber-200/90">LLM: {importLlmWarn}</p>
      )}
      {!importLlmWarn &&
        savedOk === "대시보드 프로필을 이 학생에 반영했습니다." && (
          <p className="text-xs text-slate-500">이름·경력 요약 등은 LLM으로 정리되었습니다.</p>
        )}

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="text-lg font-semibold text-white">기본 정보 · 이력 (개인정보는 내부 관리용)</h2>
        <form
          key={`profile-${dataRevision}`}
          onSubmit={saveProfile}
          className="mt-4 grid gap-3 sm:grid-cols-2"
        >
          <label className="text-sm">
            <span className="text-slate-400">이름</span>
            <input
              name="display_name"
              defaultValue={s.display_name}
              required
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-400">이메일</span>
            <input
              name="email"
              type="email"
              defaultValue={s.email ?? ""}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-400">연락처</span>
            <input
              name="phone"
              defaultValue={s.phone ?? ""}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-400">학교·과정</span>
            <input
              name="school"
              defaultValue={s.school ?? ""}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="text-slate-400">컨설턴트 메모 (내부)</span>
            <textarea
              name="memo"
              rows={2}
              defaultValue={s.memo ?? ""}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="text-slate-400">이력서 본문</span>
            <textarea
              name="resume_text"
              rows={5}
              defaultValue={s.resume_text ?? ""}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="text-slate-400">경력 요약</span>
            <textarea
              name="career_summary"
              rows={3}
              defaultValue={s.career_summary ?? ""}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-400">타깃 직군</span>
            <select
              name="target_category"
              defaultValue={s.target_category}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            >
              {categories.length === 0 && (
                <>
                  <option value="data_analyst">데이터 분석가</option>
                  <option value="ai_engineer">AI 엔지니어</option>
                  <option value="backend_developer">백엔드</option>
                </>
              )}
              {categories.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label}
                </option>
              ))}
              {!categories.some((c) => c.slug === s.target_category) && s.target_category && (
                <option value={s.target_category}>(현재) {s.target_category}</option>
              )}
              <option value="all">전체 직군 공고(비권장)</option>
            </select>
          </label>
          <p className="text-xs text-slate-500 sm:col-span-2">
            직군 목록은 컨설턴트 보드에서 추가·삭제할 수 있습니다.
          </p>
          <label className="text-sm">
            <span className="text-slate-400">최종 목표 달성률 (%)</span>
            <input
              name="final_goal_progress"
              type="number"
              min={0}
              max={100}
              step={1}
              defaultValue={s.final_goal_progress}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
            />
          </label>
          <div className="sm:col-span-2">
            <button
              type="submit"
              className="rounded-lg border border-sky-800 bg-sky-950/50 px-4 py-2 text-sm text-sky-200"
            >
              프로필 저장
            </button>
          </div>
        </form>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/20 p-4">
          <h2 className="text-lg font-semibold text-emerald-200">어필 포인트</h2>
          <p className="mt-1 text-xs text-slate-500">수집 공고 상위 수요 스킬 대비 이력서에 드러난 강점</p>
          <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-slate-300">
            {data.appeal_points.length ? (
              data.appeal_points.map((x, i) => <li key={i}>{x}</li>)
            ) : (
              <li className="text-slate-500">이력서를 입력하면 자동 산출됩니다.</li>
            )}
          </ul>
        </div>
        <div className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-4">
          <h2 className="text-lg font-semibold text-amber-200">보완점</h2>
          <p className="mt-1 text-xs text-slate-500">상위 수요인데 이력서 규칙 추출에 약하게 잡힌 영역</p>
          <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-slate-300">
            {data.improvement_points.length ? (
              data.improvement_points.map((x, i) => <li key={i}>{x}</li>)
            ) : (
              <li className="text-slate-500">데이터가 없습니다.</li>
            )}
          </ul>
        </div>
      </section>

      {data.preparation_notes.length > 0 && (
        <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <h2 className="text-lg font-semibold text-white">준비 가이드 (자동)</h2>
          <ul className="mt-2 list-inside list-disc text-sm text-slate-400">
            {data.preparation_notes.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="text-lg font-semibold text-white">희망 기업</h2>
        <form onSubmit={addCompany} className="mt-2 flex flex-wrap gap-2">
          <input
            value={coName}
            onChange={(e) => setCoName(e.target.value)}
            placeholder="기업명"
            className="max-w-xs rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
          />
          <button
            type="submit"
            className="rounded-lg border border-violet-800 bg-violet-950/40 px-3 py-2 text-sm text-violet-200"
          >
            추가
          </button>
        </form>
        <ul className="mt-3 space-y-2">
          {data.target_companies.map((c) => (
            <li
              key={c.id}
              className="flex items-center justify-between gap-2 rounded border border-slate-800 bg-slate-950/50 px-3 py-2 text-sm"
            >
              <span className="text-slate-200">{c.company_name}</span>
              <button type="button" onClick={() => removeCompany(c.id)} className="text-xs text-red-400">
                삭제
              </button>
            </li>
          ))}
          {data.target_companies.length === 0 && (
            <li className="text-sm text-slate-500">등록된 희망 기업이 없습니다.</li>
          )}
        </ul>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="text-lg font-semibold text-white">현재 스펙으로 지원 가능한 공고 (상위)</h2>
        <p className="mt-1 text-xs text-slate-500">DB 수집 공고와 이력서 스킬·자격 메타 매칭 점수 기준</p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="py-2 pr-2">점수</th>
                <th className="py-2 pr-2">회사</th>
                <th className="py-2 pr-2">공고</th>
                <th className="py-2">미충족 자격(일부)</th>
              </tr>
            </thead>
            <tbody>
              {data.eligible_jobs.map((j) => (
                <tr key={j.job_id} className="border-b border-slate-800/80">
                  <td className="py-2 pr-2 text-sky-300">{j.match_score.toFixed(1)}</td>
                  <td className="py-2 pr-2 text-slate-300">{j.company}</td>
                  <td className="py-2 pr-2">
                    <Link href={`/job/${j.job_id}`} className="text-sky-400 hover:underline">
                      {j.title}
                    </Link>
                  </td>
                  <td className="py-2 text-xs text-amber-200/80">
                    {(j.requirements_mismatch ?? []).slice(0, 3).join(" · ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.eligible_jobs.length === 0 && (
            <p className="text-sm text-slate-500">이력서를 넣거나 공고를 수집해 주세요.</p>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-teal-900/40 bg-teal-950/15 p-4">
        <h2 className="text-lg font-semibold text-teal-200">희망 기업과 겹치는 공고 (합격 라인업 후보)</h2>
        <p className="mt-1 text-xs text-slate-500">희망 기업명과 정확히 일치하는 회사명 공고만 표시합니다.</p>
        <ul className="mt-3 space-y-2 text-sm">
          {data.target_aligned_jobs.map((j) => (
            <li key={j.job_id} className="flex flex-wrap items-baseline gap-2 text-slate-300">
              <span className="font-medium text-teal-100">{j.company}</span>
              <Link href={`/job/${j.job_id}`} className="text-sky-400 hover:underline">
                {j.title}
              </Link>
              <span className="text-slate-500">점수 {j.match_score.toFixed(1)}</span>
            </li>
          ))}
          {data.target_aligned_jobs.length === 0 && (
            <li className="text-slate-500">희망 기업을 등록하거나, 수집 공고에 해당 회사가 있는지 확인하세요.</li>
          )}
        </ul>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="text-lg font-semibold text-white">이번 달 달성 목표</h2>
        <form key={`month-${dataRevision}`} onSubmit={saveMonthGoal} className="mt-3 space-y-2">
          <label className="block text-xs text-slate-500">추가 준비 자격증</label>
          <textarea
            name="certifications"
            rows={2}
            defaultValue={mg?.certifications ?? ""}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
          />
          <label className="block text-xs text-slate-500">추가 학습 역량</label>
          <textarea
            name="competencies"
            rows={2}
            defaultValue={mg?.competencies ?? ""}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
          />
          <label className="block text-xs text-slate-500">이력서·지원 영역</label>
          <textarea
            name="application_areas"
            rows={2}
            defaultValue={mg?.application_areas ?? ""}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-200"
          />
          <input type="hidden" name="ym" value={ym} readOnly />
          <button
            type="submit"
            className="rounded-lg border border-amber-800/80 bg-amber-950/30 px-3 py-2 text-sm text-amber-100"
          >
            이번 달 목표 저장 ({ym})
          </button>
        </form>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="text-lg font-semibold text-white">개인 일정</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {data.personal_events.map((ev) => (
            <li
              key={ev.id}
              className="flex flex-wrap items-start justify-between gap-2 rounded border border-slate-800/60 bg-slate-950/40 px-3 py-2"
            >
              <div>
                <span className="text-slate-500">{EVENT_TYPE_KO[ev.event_type] ?? ev.event_type}</span>
                <p className="text-slate-200">{ev.title}</p>
                <p className="text-xs text-slate-500">
                  {new Date(ev.starts_at).toLocaleString("ko-KR")}
                  {ev.company_name ? ` · ${ev.company_name}` : ""}
                </p>
              </div>
              <button type="button" onClick={() => removeEvent(ev.id)} className="text-xs text-red-400">
                삭제
              </button>
            </li>
          ))}
          {data.personal_events.length === 0 && (
            <li className="text-slate-500">일정이 없습니다. 보드에서 추가할 수 있습니다.</li>
          )}
        </ul>
      </section>

      <section className="rounded-xl border border-red-900/40 bg-red-950/20 p-4">
        <h2 className="text-lg font-semibold text-red-200">학생 삭제</h2>
        <p className="mt-1 text-sm text-slate-400">
          삭제 후에는 복구할 수 없습니다. 일정·월간 목표·희망 기업 데이터가 함께 제거됩니다.
        </p>
        <button
          type="button"
          onClick={removeStudent}
          className="mt-3 rounded-lg border border-red-800 bg-red-950/50 px-4 py-2 text-sm text-red-200 hover:bg-red-900/40"
        >
          이 학생 삭제
        </button>
      </section>
    </div>
  );
}
