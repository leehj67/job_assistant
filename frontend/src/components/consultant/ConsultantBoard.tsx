"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createConsultantStudent,
  deleteConsultantCategory,
  deleteConsultantEvent,
  deleteConsultantStudent,
  getConsultantCategories,
  getConsultantDashboard,
  postConsultantCategory,
  postConsultantStudentEvent,
  consultantImportLlmHint,
  postImportFromApplicantProfile,
  putConsultantMonthlyGoal,
  type ConsultantCalendarEvent,
  type ConsultantCategoryItem,
  type ConsultantDashboard,
  type ConsultantMonthlyGoal,
  type ConsultantStudent,
} from "@/lib/api";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

const EVENT_TYPE_KO: Record<string, string> = {
  exam: "시험",
  application_deadline: "지원 마감",
  interview: "면접",
  other: "기타",
};

function pad(n: number) {
  return n < 10 ? `0${n}` : `${n}`;
}

function studentColor(id: number): string {
  const hues = [200, 160, 280, 40, 320, 120];
  const h = hues[id % hues.length];
  return `hsl(${h} 55% 35%)`;
}

function categoryLabel(slug: string, cats: ConsultantCategoryItem[]): string {
  const f = cats.find((c) => c.slug === slug);
  return f?.label ?? slug;
}

export function ConsultantBoard() {
  const now = new Date();
  const [y, setY] = useState(now.getFullYear());
  const [m, setM] = useState(now.getMonth() + 1);
  const [data, setData] = useState<ConsultantDashboard | null>(null);
  const [categories, setCategories] = useState<ConsultantCategoryItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [importNotice, setImportNotice] = useState<{
    text: string;
    variant: "ok" | "warn";
    /** 새 학생 가져오기 직후 상세로 안내 */
    newStudentId?: number;
    newStudentName?: string;
  } | null>(null);
  /** 대시보드 프로필 가져오기 진행 중 (LLM 포함 시 수 분 걸릴 수 있음) */
  const [importBusy, setImportBusy] = useState<"new" | "existing" | null>(null);
  const [loading, setLoading] = useState(true);

  const [newName, setNewName] = useState("");
  const [newCat, setNewCat] = useState("data_analyst");

  const [newCatSlug, setNewCatSlug] = useState("");
  const [newCatLabel, setNewCatLabel] = useState("");
  const [importIntoId, setImportIntoId] = useState<number | "">("");

  const [evStudentId, setEvStudentId] = useState<number | "">("");
  const [evTitle, setEvTitle] = useState("");
  const [evType, setEvType] = useState<"exam" | "application_deadline" | "interview" | "other">(
    "application_deadline"
  );
  const [evStart, setEvStart] = useState("");
  const [evCompany, setEvCompany] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const d = await getConsultantDashboard(y, m);
      setData(d);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "불러오기 실패";
      setErr(
        `${msg} — 백엔드(http://127.0.0.1:8000)가 켜져 있는지, 최신 코드로 재기동했는지 확인하세요.`
      );
      setData({ year: y, month: m, year_month: `${y}-${pad(m)}`, students: [], events: [], monthly_goals: [] });
    } finally {
      setLoading(false);
    }
  }, [y, m]);

  useEffect(() => {
    load();
  }, [load]);

  const loadCategories = useCallback(async () => {
    try {
      const c = await getConsultantCategories();
      setCategories(c);
    } catch {
      /* 보드는 카테고리 없이도 동작 */
    }
  }, []);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  const goalsByStudent = useMemo(() => {
    const map = new Map<number, ConsultantMonthlyGoal>();
    if (!data) return map;
    for (const g of data.monthly_goals) {
      map.set(g.student_id, g);
    }
    return map;
  }, [data]);

  const eventsByDay = useMemo(() => {
    const map = new Map<string, ConsultantCalendarEvent[]>();
    if (!data) return map;
    for (const e of data.events) {
      const d = new Date(e.starts_at);
      if (d.getFullYear() !== y || d.getMonth() + 1 !== m) continue;
      const key = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
      const arr = map.get(key) ?? [];
      arr.push(e);
      map.set(key, arr);
    }
    return map;
  }, [data, y, m]);

  const grid = useMemo(() => {
    const first = new Date(y, m - 1, 1);
    const startPad = first.getDay();
    const lastDate = new Date(y, m, 0).getDate();
    const cells: { day: number | null; key: string }[] = [];
    for (let i = 0; i < startPad; i++) cells.push({ day: null, key: `p${i}` });
    for (let d = 1; d <= lastDate; d++) {
      cells.push({
        day: d,
        key: `${y}-${pad(m)}-${pad(d)}`,
      });
    }
    return cells;
  }, [y, m]);

  async function onSaveGoal(s: ConsultantStudent) {
    if (!data) return;
    const certs = (document.getElementById(`goal-certs-${s.id}`) as HTMLTextAreaElement)?.value ?? "";
    const comp = (document.getElementById(`goal-comp-${s.id}`) as HTMLTextAreaElement)?.value ?? "";
    const areas =
      (document.getElementById(`goal-areas-${s.id}`) as HTMLTextAreaElement)?.value ?? "";
    setErr(null);
    try {
      await putConsultantMonthlyGoal(s.id, data.year_month, {
        certifications: certs,
        competencies: comp,
        application_areas: areas,
      });
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "목표 저장 실패");
    }
  }

  async function onAddStudent(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setErr(null);
    try {
      await createConsultantStudent({
        display_name: newName.trim(),
        target_category: newCat,
      });
      setNewName("");
      await load();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "학생 추가 실패");
    }
  }

  async function onDeleteStudent(id: number, name: string) {
    if (!confirm(`「${name}」 학생을 삭제할까요? 일정·목표·희망기업까지 모두 삭제됩니다.`)) return;
    setErr(null);
    try {
      await deleteConsultantStudent(id);
      await load();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "삭제 실패");
    }
  }

  async function onImportNewStudent() {
    setErr(null);
    setImportNotice(null);
    setImportBusy("new");
    try {
      const { importLlmStatus, student } = await postImportFromApplicantProfile({});
      const llmHint = consultantImportLlmHint(importLlmStatus);
      setImportNotice(
        llmHint
          ? {
              text: `가져오기 완료. ${llmHint}`,
              variant: "warn",
              newStudentId: student.id,
              newStudentName: student.display_name,
            }
          : {
              text: "가져오기 완료. LLM으로 이름·경력 요약 등을 정리했습니다.",
              variant: "ok",
              newStudentId: student.id,
              newStudentName: student.display_name,
            }
      );
      await load();
      await loadCategories();
    } catch (x) {
      const raw = x instanceof Error ? x.message : "가져오기 실패";
      setErr(
        `${raw} — 대시보드에서 「프로필에 저장」을 했는지, 이력서/경력 요약이 비어 있지 않은지 확인하세요.`
      );
    } finally {
      setImportBusy(null);
    }
  }

  async function onImportIntoExisting() {
    if (importIntoId === "") return;
    setErr(null);
    setImportNotice(null);
    setImportBusy("existing");
    try {
      const { importLlmStatus } = await postImportFromApplicantProfile({
        student_id: Number(importIntoId),
      });
      const llmHint = consultantImportLlmHint(importLlmStatus);
      setImportNotice(
        llmHint
          ? { text: `덮어쓰기 완료. ${llmHint}`, variant: "warn" }
          : { text: "덮어쓰기 완료. LLM으로 필드를 정리했습니다.", variant: "ok" }
      );
      await load();
    } catch (x) {
      const raw = x instanceof Error ? x.message : "가져오기 실패";
      setErr(`${raw} — 백엔드·Ollama 연결과 대시보드 프로필 저장 여부를 확인하세요.`);
    } finally {
      setImportBusy(null);
    }
  }

  async function onAddCategory(e: React.FormEvent) {
    e.preventDefault();
    if (!newCatSlug.trim() || !newCatLabel.trim()) return;
    setErr(null);
    try {
      await postConsultantCategory({ slug: newCatSlug.trim().toLowerCase(), label_ko: newCatLabel.trim() });
      setNewCatSlug("");
      setNewCatLabel("");
      await loadCategories();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "직군 추가 실패");
    }
  }

  async function onDeleteCategoryItem(id: number) {
    if (!confirm("이 추가 직군을 삭제할까요? (학생에 이미 설정된 slug는 그대로 유지됩니다)")) return;
    setErr(null);
    try {
      await deleteConsultantCategory(id);
      await loadCategories();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "삭제 실패");
    }
  }

  async function onAddEvent(e: React.FormEvent) {
    e.preventDefault();
    if (evStudentId === "" || !evTitle.trim() || !evStart) return;
    setErr(null);
    try {
      await postConsultantStudentEvent(Number(evStudentId), {
        title: evTitle.trim(),
        event_type: evType,
        starts_at: new Date(evStart).toISOString(),
        company_name: evCompany.trim() || null,
      });
      setEvTitle("");
      setEvCompany("");
      await load();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "일정 추가 실패");
    }
  }

  async function onDeleteEvent(id: number) {
    if (!confirm("이 일정을 삭제할까요?")) return;
    setErr(null);
    try {
      await deleteConsultantEvent(id);
      await load();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "삭제 실패");
    }
  }

  function prevMonth() {
    if (m === 1) {
      setY((x) => x - 1);
      setM(12);
    } else setM((x) => x - 1);
  }

  function nextMonth() {
    if (m === 12) {
      setY((x) => x + 1);
      setM(1);
    } else setM((x) => x + 1);
  }

  return (
    <div className="space-y-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">컨설턴트 보드</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            맡은 학생 목록·월간 캘린더·이번 달 달성 목표를 한 화면에서 관리합니다. 학생 이름을 누르면 상세에서 수정·삭제할
            수 있습니다.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          <Link
            href="/"
            className="rounded-lg border border-slate-600 bg-slate-900 px-4 py-2 text-center text-sm text-slate-200 hover:bg-slate-800"
          >
            ← 이력서 대시보드로
          </Link>
          {importBusy && (
            <div
              role="status"
              aria-live="polite"
              className="max-w-md rounded-lg border border-sky-800 bg-sky-950/50 px-3 py-2 text-sm text-sky-100"
            >
              <span
                className="mr-2 inline-block size-4 animate-spin rounded-full border-2 border-sky-400 border-t-transparent align-[-3px]"
                aria-hidden
              />
              {importBusy === "new"
                ? "대시보드 프로필을 새 학생으로 가져오는 중…"
                : "선택한 학생에 프로필을 덮어쓰는 중…"}
              <span className="mt-1 block text-xs text-sky-200/85">
                AI(Ollama/OpenAI)로 필드를 정리하면 30초~수 분 걸릴 수 있습니다. 완료될 때까지 기다려 주세요.
              </span>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onImportNewStudent}
              disabled={importBusy !== null}
              className="rounded-lg border border-violet-800 bg-violet-950/40 px-3 py-2 text-sm text-violet-200 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {importBusy === "new" ? "가져오는 중…" : "대시보드 프로필 → 새 학생"}
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <select
              value={importIntoId === "" ? "" : String(importIntoId)}
              onChange={(e) => setImportIntoId(e.target.value ? Number(e.target.value) : "")}
              disabled={importBusy !== null}
              className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-slate-200 disabled:opacity-50"
            >
              <option value="">기존 학생 선택…</option>
              {(data?.students ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.display_name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={onImportIntoExisting}
              disabled={importIntoId === "" || importBusy !== null}
              className="rounded-lg border border-violet-700/60 px-3 py-2 text-violet-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {importBusy === "existing" ? "덮어쓰는 중…" : "프로필 덮어쓰기"}
            </button>
          </div>
        </div>
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="text-lg font-semibold text-white">타깃 직군(카테고리) 추가</h2>
        <p className="mt-1 text-xs text-slate-500">
          기본 3직군 외에 슬러그(영문·밑줄)와 한글 이름을 등록하면 학생 추가·상세에서 선택할 수 있습니다.
        </p>
        <form onSubmit={onAddCategory} className="mt-3 flex flex-wrap items-end gap-2">
          <label className="text-sm">
            <span className="text-slate-400">slug</span>
            <input
              value={newCatSlug}
              onChange={(e) => setNewCatSlug(e.target.value)}
              placeholder="frontend_dev"
              className="mt-1 block w-40 rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 font-mono text-sm text-slate-200"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-400">표시 이름</span>
            <input
              value={newCatLabel}
              onChange={(e) => setNewCatLabel(e.target.value)}
              placeholder="프론트엔드 개발자"
              className="mt-1 block min-w-[12rem] rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-200"
            />
          </label>
          <button
            type="submit"
            className="rounded-lg border border-emerald-800 bg-emerald-950/40 px-3 py-2 text-sm text-emerald-200"
          >
            직군 등록
          </button>
        </form>
        <ul className="mt-3 flex flex-wrap gap-2 text-xs">
          {categories
            .filter((c) => !c.is_builtin && c.id != null)
            .map((c) => (
              <li
                key={c.id}
                className="flex items-center gap-1 rounded-full border border-slate-700 bg-slate-950 px-2 py-1 text-slate-300"
              >
                <span className="font-mono text-slate-500">{c.slug}</span>
                <span>{c.label}</span>
                <button
                  type="button"
                  onClick={() => c.id != null && onDeleteCategoryItem(c.id)}
                  className="ml-1 text-red-400 hover:text-red-300"
                >
                  ×
                </button>
              </li>
            ))}
        </ul>
      </section>

      {err && (
        <p className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-2 text-sm text-red-200">{err}</p>
      )}
      {importNotice && (
        <div
          className={
            importNotice.variant === "ok"
              ? "space-y-2 rounded-lg border border-emerald-900/50 bg-emerald-950/30 px-4 py-2 text-sm text-emerald-100"
              : "space-y-2 rounded-lg border border-amber-900/40 bg-amber-950/30 px-4 py-2 text-sm text-amber-100"
          }
        >
          <p>{importNotice.text}</p>
          {importNotice.newStudentId != null && (
            <p>
              <Link
                href={`/consultant/students/${importNotice.newStudentId}`}
                className="font-medium text-sky-400 underline hover:text-sky-300"
              >
                「{importNotice.newStudentName ?? "새 학생"}」 상세 열기 →
              </Link>
            </p>
          )}
        </div>
      )}

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-white">월간 일정</h2>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={prevMonth}
              className="rounded-lg border border-slate-700 px-3 py-1 text-sm text-slate-200 hover:bg-slate-800"
            >
              이전
            </button>
            <span className="min-w-[8rem] text-center text-slate-200">
              {y}년 {m}월
            </span>
            <button
              type="button"
              onClick={nextMonth}
              className="rounded-lg border border-slate-700 px-3 py-1 text-sm text-slate-200 hover:bg-slate-800"
            >
              다음
            </button>
          </div>
        </div>

        {loading && !data ? (
          <p className="text-slate-500">불러오는 중…</p>
        ) : (
          <>
            <div className="grid grid-cols-7 gap-1 text-center text-xs font-medium text-slate-500">
              {WEEKDAYS.map((w) => (
                <div key={w} className="py-2">
                  {w}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-1">
              {grid.map((cell) => (
                <div
                  key={cell.key}
                  className="min-h-[5.5rem] rounded-md border border-slate-800/80 bg-slate-950/50 p-1 text-left"
                >
                  {cell.day !== null && (
                    <>
                      <div className="text-xs font-medium text-slate-400">{cell.day}</div>
                      <ul className="mt-1 space-y-0.5">
                        {(eventsByDay.get(cell.key) ?? []).slice(0, 4).map((ev) => (
                          <li key={ev.id} className="truncate text-[10px] leading-tight">
                            <span
                              className="inline-block h-1.5 w-1.5 shrink-0 rounded-full align-middle"
                              style={{ backgroundColor: studentColor(ev.student_id) }}
                            />
                            <span className="ml-0.5 text-slate-300">{ev.student_name}</span>
                            <span className="text-slate-500"> · {EVENT_TYPE_KO[ev.event_type] ?? ev.event_type}</span>
                            <br />
                            <span className="text-slate-400">{ev.title}</span>
                            {ev.company_name && (
                              <span className="block truncate text-slate-500">({ev.company_name})</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              ))}
            </div>

            <div className="mt-4 space-y-2 border-t border-slate-800 pt-4">
              <p className="text-xs font-medium text-slate-500">이번 달 일정 목록</p>
              <ul className="max-h-48 space-y-2 overflow-y-auto text-sm">
                {(data?.events ?? []).map((ev) => (
                  <li
                    key={ev.id}
                    className="flex flex-wrap items-start justify-between gap-2 rounded border border-slate-800/60 bg-slate-950/40 px-2 py-1.5"
                  >
                    <div>
                      <span className="font-medium text-slate-200">{ev.student_name}</span>
                      <span className="text-slate-500"> · {EVENT_TYPE_KO[ev.event_type] ?? ev.event_type}</span>
                      <p className="text-slate-300">{ev.title}</p>
                      <p className="text-xs text-slate-500">
                        {new Date(ev.starts_at).toLocaleString("ko-KR")}
                        {ev.company_name ? ` · ${ev.company_name}` : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onDeleteEvent(ev.id)}
                      className="shrink-0 text-xs text-red-400 hover:text-red-300"
                    >
                      삭제
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="text-lg font-semibold text-white">일정 빠르게 추가</h2>
        <form onSubmit={onAddEvent} className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-sm">
            <span className="text-slate-400">학생</span>
            <select
              value={evStudentId}
              onChange={(e) => setEvStudentId(e.target.value ? Number(e.target.value) : "")}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-slate-200"
            >
              <option value="">선택</option>
              {(data?.students ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="text-slate-400">유형</span>
            <select
              value={evType}
              onChange={(e) => setEvType(e.target.value as typeof evType)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-slate-200"
            >
              <option value="exam">시험</option>
              <option value="application_deadline">지원 마감</option>
              <option value="interview">면접</option>
              <option value="other">기타</option>
            </select>
          </label>
          <label className="text-sm sm:col-span-2 lg:col-span-1">
            <span className="text-slate-400">일시</span>
            <input
              type="datetime-local"
              value={evStart}
              onChange={(e) => setEvStart(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-slate-200"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="text-slate-400">제목</span>
            <input
              value={evTitle}
              onChange={(e) => setEvTitle(e.target.value)}
              placeholder="예: 네이버 백엔드 서류 마감"
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-slate-200"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="text-slate-400">기업명 (선택)</span>
            <input
              value={evCompany}
              onChange={(e) => setEvCompany(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-slate-200"
            />
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              className="rounded-lg border border-sky-800 bg-sky-950/50 px-4 py-2 text-sm text-sky-200 hover:bg-sky-900/40"
            >
              일정 추가
            </button>
          </div>
        </form>
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-lg font-semibold text-white">학생별 이번 달 달성 목표</h2>
          <form onSubmit={onAddStudent} className="flex flex-wrap items-end gap-2">
            <label className="text-sm">
              <span className="text-slate-400">새 학생</span>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="이름"
                className="mt-1 rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-slate-200"
              />
            </label>
            <select
              value={newCat}
              onChange={(e) => setNewCat(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-200"
            >
              {(categories.length ? categories : [{ slug: "data_analyst", label: "데이터 분석가", is_builtin: true, id: null }]).map(
                (c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.label}
                  </option>
                )
              )}
            </select>
            <button
              type="submit"
              className="rounded-lg border border-emerald-800 bg-emerald-950/40 px-3 py-2 text-sm text-emerald-200"
            >
              추가
            </button>
          </form>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {(data?.students ?? []).map((s) => {
            const g = goalsByStudent.get(s.id);
            return (
              <div
                key={s.id}
                className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 shadow-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <Link
                      href={`/consultant/students/${s.id}`}
                      className="text-lg font-semibold text-sky-300 hover:text-sky-200 hover:underline"
                    >
                      {s.display_name}
                    </Link>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Link
                        href={`/consultant/students/${s.id}`}
                        className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
                      >
                        상세·수정
                      </Link>
                      <button
                        type="button"
                        onClick={() => onDeleteStudent(s.id, s.display_name)}
                        className="rounded border border-red-900/60 px-2 py-1 text-xs text-red-300 hover:bg-red-950/40"
                      >
                        삭제
                      </button>
                    </div>
                  </div>
                  <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-400">
                    {categoryLabel(s.target_category, categories)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  최종 목표 달성률(수동) {s.final_goal_progress}% — 상세에서 조정
                </p>

                <div className="mt-3 space-y-2">
                  <label className="block text-xs font-medium text-slate-500">추가 준비 자격증</label>
                  <textarea
                    id={`goal-certs-${s.id}`}
                    key={`c-${s.id}-${g?.id ?? "n"}`}
                    defaultValue={g?.certifications ?? ""}
                    rows={2}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-200"
                    placeholder="예: SQLD, 빅데이터분석기사"
                  />
                  <label className="block text-xs font-medium text-slate-500">추가 학습 역량</label>
                  <textarea
                    id={`goal-comp-${s.id}`}
                    key={`m-${s.id}-${g?.id ?? "n"}`}
                    defaultValue={g?.competencies ?? ""}
                    rows={2}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-200"
                    placeholder="예: PyTorch 튜토리얼 2주, Docker 기초"
                  />
                  <label className="block text-xs font-medium text-slate-500">이력서·지원 영역</label>
                  <textarea
                    id={`goal-areas-${s.id}`}
                    key={`a-${s.id}-${g?.id ?? "n"}`}
                    defaultValue={g?.application_areas ?? ""}
                    rows={2}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-200"
                    placeholder="예: 데이터 플랫폼 팀, 추천/검색 PoC"
                  />
                  <button
                    type="button"
                    onClick={() => onSaveGoal(s)}
                    className="rounded-lg border border-amber-800/80 bg-amber-950/30 px-3 py-1.5 text-sm text-amber-100"
                  >
                    이번 달 목표 저장
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {data && data.students.length === 0 && (
          <p className="text-sm text-slate-500">등록된 학생이 없습니다. 위에서 이름을 넣고 추가해 보세요.</p>
        )}
      </section>
    </div>
  );
}
