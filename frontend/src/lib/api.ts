/** SSR용 백엔드 origin (끝에 /api 가 붙어 있으면 제거 — /api/api/... 404 방지) */
function serverOrigin(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  let u = raw.trim().replace(/\/+$/, "");
  if (u.endsWith("/api")) u = u.slice(0, -4);
  return u;
}

/** 브라우저: 동일 출처 `/api` → `app/api/[...path]/route.ts` 프록시. SSR: 백엔드 직접 URL. */
function apiBase(): string {
  if (typeof window !== "undefined") {
    return "";
  }
  return serverOrigin();
}

function browserDirectOrigin(): string | null {
  if (typeof window === "undefined") return null;
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (!raw) return null;
  let u = raw.trim().replace(/\/+$/, "");
  if (u.endsWith("/api")) u = u.slice(0, -4);
  return u || null;
}

/**
 * PDF 등 대용량 multipart는 Next 프록시(`app/api/[...path]`)를 거치면 환경에 따라 본문이 잘리거나 실패할 수 있음.
 * env 미설정 시에도 로컬 호스트에서는 기본 백엔드 포트로 직접 전송해 우회한다.
 */
function browserLargeUploadOrigin(): string {
  const direct = browserDirectOrigin();
  if (direct) return direct;
  if (typeof window === "undefined") return serverOrigin();
  const h = window.location.hostname;
  if (h === "localhost" || h === "127.0.0.1") {
    return "http://127.0.0.1:8000";
  }
  return "";
}

/** 브라우저+로컬에서는 백엔드로 직접 호출해 최신 라우트를 쓰고 Next 프록시를 우회. */
function browserBackendApiPath(apiPath: string): string {
  const p = apiPath.startsWith("/") ? apiPath : `/${apiPath}`;
  const origin = browserLargeUploadOrigin();
  if (origin) return `${origin.replace(/\/+$/, "")}${p}`;
  return `${apiBase()}${p}`;
}

function parseFastApiDetail(t: unknown): string | null {
  if (!t || typeof t !== "object") return null;
  const d = (t as { detail?: unknown }).detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    const parts = d
      .map((x) => {
        if (x && typeof x === "object" && "msg" in x && typeof (x as { msg: unknown }).msg === "string") {
          return (x as { msg: string }).msg;
        }
        return null;
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  return null;
}

async function fetchJson<T>(path: string): Promise<T> {
  const r = await fetch(`${apiBase()}${path}`, { next: { revalidate: 60 } });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json() as Promise<T>;
}

export type CategoryItem = { slug: string; label: string };

export type Overview = {
  job_counts_by_category: Record<string, number>;
  top_demand_categories: [string, number][];
  rising_interest_keywords: string[];
  opportunity_keywords: string[];
  oversaturated_keywords: string[];
};

export type GapItem = {
  keyword: string;
  demand_score: number;
  interest_score: number;
  gap_type: string;
  gap_label_ko: string;
};

export type TrendSeries = {
  keyword: string;
  points: { date: string; interest_score: number }[];
};

export type SkillStat = {
  normalized_skill: string;
  skill_group: string;
  count: number;
};

export type Recommendation = {
  id: number;
  target_type: string;
  category: string;
  title: string;
  content: string;
  generated_at: string;
};

export function getCategories() {
  return fetchJson<CategoryItem[]>("/api/categories");
}

export function getOverview() {
  return fetchJson<Overview>("/api/overview");
}

export function getGap(category: string) {
  return fetchJson<GapItem[]>(`/api/analysis/gap?category=${encodeURIComponent(category)}`);
}

export function getTrendSeries(category: string, keywords: string[]) {
  const q = keywords.join(",");
  return fetchJson<TrendSeries[]>(
    `/api/trends/series?category=${encodeURIComponent(category)}&keywords=${encodeURIComponent(q)}`
  );
}

export function getSkillStats(category: string) {
  return fetchJson<SkillStat[]>(
    `/api/jobs/stats/skills?category=${encodeURIComponent(category)}`
  );
}

export function getRecommendations(category: string, target?: "academy" | "jobseeker") {
  const t = target ? `&target_type=${target}` : "";
  return fetchJson<Recommendation[]>(
    `/api/recommendations?category=${encodeURIComponent(category)}${t}`
  );
}

export type CollectBody = {
  keywords: string[];
  category: string;
  sources: ("saramin" | "jobkorea")[];
  max_pages: number;
  fetch_detail?: boolean;
  use_ocr?: boolean;
};

export type CollectedJobLink = {
  id: number;
  title: string;
  company: string;
  source: string;
  url: string | null;
};

export type CollectResult = {
  jobs_fetched: number;
  jobs_new: number;
  job_ids: number[];
  errors: string[];
  /** 백엔드 최신 버전에서만 포함 */
  job_links?: CollectedJobLink[];
};

/** 수집은 사이트 응답에 따라 매우 길어질 수 있음. 0이면 브라우저/프록시 기본(무제한에 가깝게) */
export const COLLECT_FETCH_TIMEOUT_MS = 8 * 60 * 1000;

export async function postCollect(
  body: CollectBody,
  signal?: AbortSignal
): Promise<CollectResult> {
  const direct = browserDirectOrigin();
  const endpoint = direct ? `${direct}/api/collect` : `${apiBase()}/api/collect`;
  const r = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      fetch_detail: false,
      use_ocr: true,
      ...body,
    }),
    signal,
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const t = await r.text();
      if (t) msg = t.length > 500 ? t.slice(0, 500) + "…" : t;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<CollectResult>;
}

export function getLlmStatus() {
  return fetchJson<{
    openai_configured: boolean;
    ollama_enabled: boolean;
    ollama_base_url: string;
    ollama_model: string;
    ollama_reachable: boolean;
  }>("/api/llm/status");
}

export type KeywordAnalysis = {
  job_id: number;
  title: string;
  company: string;
  category: string;
  form_summary: {
    work_location: string | null;
    salary: string | null;
    career: Record<string, unknown> | null;
    requirements_lines: number;
    preferred_lines: number;
    responsibilities_lines: number;
  };
  analyzed_char_length: number;
  technical_terms: {
    term: string;
    count: number;
    group: string;
    group_label_ko: string;
    normalized?: string | null;
    section?: string | null;
    confidence?: number | null;
  }[];
  group_distribution: { group: string; label_ko: string; count: number }[];
  word_frequency: { token: string; count: number }[];
  soft_skills?: { phrase: string; section: string | null }[];
  pipeline?: {
    stage1: {
      rake_phrases: string[];
      yake: { phrase: string; score: number; source: string }[];
      kiwi_morph_tokens: string[];
      kobert_subword_candidates: string[];
      combined_candidates: string[];
      counts: Record<string, number>;
    };
    stage2: {
      llm: Record<string, unknown> | null;
      error: string | null;
      ollama_reachable: boolean;
      openai_configured: boolean;
    };
  };
};

export async function getJobKeywordAnalysis(jobId: number): Promise<KeywordAnalysis> {
  const r = await fetch(`${apiBase()}/api/jobs/${jobId}/keyword-analysis`, {
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`keyword-analysis ${r.status}`);
  return r.json() as Promise<KeywordAnalysis>;
}

export type AnalyzedKeyword = {
  keyword: string;
  jobs_count: number;
  mentions_count: number;
};

export type KeywordMatchedJob = {
  id: number;
  title: string;
  company: string;
  source: string;
  source_url: string | null;
  work_location: string | null;
  career_label: string | null;
};

export function getAnalyzedKeywords(limit = 80) {
  return fetchJson<AnalyzedKeyword[]>(`/api/keywords/analyzed?limit=${limit}`);
}

export function getJobsByKeyword(keyword: string, limit = 200) {
  return fetchJson<KeywordMatchedJob[]>(
    `/api/keywords/${encodeURIComponent(keyword)}/jobs?limit=${limit}`
  );
}

export type ResumeSkillItem = { normalized: string; skill_group: string };

export type MatchedJobItem = {
  id: number;
  title: string;
  company: string;
  category: string;
  source: string;
  source_url: string | null;
  match_score: number;
  matched_skills: string[];
  job_skill_count: number;
  /** 백엔드 구버전 응답 호환 */
  requirements_total?: number;
  requirements_mismatch?: string[];
};

export type MatchJobsBody = {
  resume_text?: string | null;
  career_summary?: string | null;
  category?: string | null;
  limit?: number;
};

export async function postApplicantMatchJobs(body: MatchJobsBody) {
  const r = await fetch(`${apiBase()}/api/applicant/match-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`match-jobs ${r.status}`);
  return r.json() as Promise<{ resume_skills: ResumeSkillItem[]; jobs: MatchedJobItem[] }>;
}

export type IndustrySkillDemand = {
  normalized_skill: string;
  skill_group: string;
  job_count: number;
};

export type PreparationInsight = {
  category: string;
  resume_skills: ResumeSkillItem[];
  industry_top_skills: IndustrySkillDemand[];
  aligned_skills: string[];
  gap_skills: string[];
  action_items: string[];
};

export async function getApplicantPreparation(category?: string | null) {
  const q =
    category && category !== "all"
      ? `?category=${encodeURIComponent(category)}`
      : "";
  const r = await fetch(`${browserBackendApiPath("/api/applicant/preparation")}${q}`, {
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`preparation ${r.status}`);
  return r.json() as Promise<PreparationInsight>;
}

export type ApplicantProfile = {
  id: number;
  display_name: string | null;
  career_years: number | null;
  career_summary: string | null;
  resume_text: string | null;
  portfolio_urls: string[];
  extra_links: Record<string, unknown> | null;
  application_prefs: Record<string, unknown> | null;
  updated_at: string | null;
};

export async function getApplicantProfile() {
  const r = await fetch(browserBackendApiPath("/api/applicant/profile"), { cache: "no-store" });
  if (!r.ok) throw new Error(`profile ${r.status}`);
  return r.json() as Promise<ApplicantProfile>;
}

export async function putApplicantProfile(body: Partial<{
  display_name: string | null;
  career_years: number | null;
  career_summary: string | null;
  resume_text: string | null;
  portfolio_urls: string[] | null;
  application_prefs: Record<string, unknown> | null;
}>) {
  const r = await fetch(browserBackendApiPath("/api/applicant/profile"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`profile put ${r.status}`);
  return r.json() as Promise<ApplicantProfile>;
}

export type ResumeDashboardCharts = {
  skill_bars: { skill: string; demand_index: number; resume_cover: number }[];
  group_radar: {
    group_key: string;
    label_ko: string;
    resume_score: number;
    market_score: number;
  }[];
  strength_gap_pie: { name: string; value: number }[];
  gap_priority_bars: { skill: string; demand_index: number; resume_cover: number }[];
};

export type CategoryFit = {
  slug: string;
  label_ko: string;
  score: number;
  reasons: string[];
};

export type CollectSuggestions = {
  search_keywords: string[];
  primary_category_slug: string;
  primary_category_label_ko: string;
  category_ranked: CategoryFit[];
  role_expansion_notes: string[];
  optional_gap_keywords: string[];
};

export async function getCollectSuggestions(analysisCategoryHint?: string | null) {
  const q =
    analysisCategoryHint && analysisCategoryHint !== "all"
      ? `?analysis_category_hint=${encodeURIComponent(analysisCategoryHint)}`
      : "";
  const r = await fetch(`${browserBackendApiPath("/api/applicant/collect-suggestions")}${q}`, {
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`collect-suggestions ${r.status}`);
  return r.json() as Promise<CollectSuggestions>;
}

export async function postCollectSuggest(body: {
  resume_text?: string | null;
  career_summary?: string | null;
  analysis_category_hint?: string | null;
}) {
  const r = await fetch(browserBackendApiPath("/api/applicant/collect-suggestions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) {
    let msg = `collect-suggestions POST ${r.status}`;
    const text = await r.text();
    try {
      const t = JSON.parse(text) as unknown;
      const parsed = parseFastApiDetail(t);
      if (parsed) msg = parsed;
    } catch {
      if (text.length && text.length < 400) msg = text;
    }
    if (r.status === 404) {
      msg += " — 백엔드를 이 프로젝트 backend에서 다시 실행했는지 확인하세요. http://127.0.0.1:8000/ 의 diagnostics.post_collect_suggestions_registered 가 true 여야 합니다.";
    }
    throw new Error(msg);
  }
  return r.json() as Promise<CollectSuggestions>;
}

export type ResumePdfAnalyzeResult = {
  extracted_char_count: number;
  text_truncated: boolean;
  resume_text: string;
  summary_paragraph: string;
  career_summary_suggested: string;
  core_skills: ResumeSkillItem[];
  career_years_estimate: number | null;
  applicable_areas: string[];
  strengths: string[];
  weaknesses: string[];
  preparation_notes: string[];
  charts: ResumeDashboardCharts;
  collect_suggestions: CollectSuggestions;
  profile_updated: boolean;
};

export async function postResumePdfAnalyze(
  file: File,
  opts: { category?: string | null; applyToProfile?: boolean }
): Promise<ResumePdfAnalyzeResult> {
  const fd = new FormData();
  fd.append("file", file, file.name || "resume.pdf");
  const cat = opts.category;
  if (cat && cat !== "all") fd.append("category", cat);
  if (opts.applyToProfile) fd.append("apply_to_profile", "true");
  const origin = browserLargeUploadOrigin();
  const url = origin
    ? `${origin.replace(/\/+$/, "")}/api/applicant/resume/analyze-pdf`
    : `${apiBase()}/api/applicant/resume/analyze-pdf`;

  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), 180_000);
  let r: Response;
  try {
    r = await fetch(url, { method: "POST", body: fd, cache: "no-store", signal: ctrl.signal });
  } catch (e) {
    clearTimeout(tid);
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error("PDF 분석 요청 시간이 초과되었습니다. 파일 크기·백엔드 기동을 확인해 주세요.");
    }
    throw e;
  }
  clearTimeout(tid);

  if (!r.ok) {
    let msg = `PDF 분석 ${r.status}`;
    const text = await r.text();
    try {
      const t = JSON.parse(text) as unknown;
      const parsed = parseFastApiDetail(t);
      if (parsed) msg = parsed;
      else if (t && typeof t === "object" && typeof (t as { error?: string }).error === "string") {
        msg = (t as { error: string }).error;
      }
    } catch {
      if (text.length && text.length < 500) msg = text;
    }
    throw new Error(msg);
  }
  return r.json() as Promise<ResumePdfAnalyzeResult>;
}

export type ResumeInsightAdjacent = {
  slug: string;
  label_ko: string;
  score: number;
  rationale?: string;
};

export type ResumeInsight = {
  summary: {
    market_fit_score: number;
    market_fit_category_slug?: string;
    market_fit_category_label?: string;
    current_best_fit_category: string;
    adjacent_categories: ResumeInsightAdjacent[];
    hard_transition_categories: ResumeInsightAdjacent[];
  };
  core_strengths: string[];
  high_impact_gaps: {
    skill: string;
    impact_score: number;
    demand_score?: number;
    reason?: string;
    section_profile?: Record<string, number>;
  }[];
  optional_gaps: Record<string, unknown>[];
  differentiator_gaps: Record<string, unknown>[];
  differentiator_assets: {
    skill: string;
    demand_score: number;
    interest_score: number;
    reason?: string;
  }[];
  market_positioning: { fit_label: string; fit_reason: string };
  path_recommendations: string[];
  action_plan: {
    immediate_actions: string[];
    mid_term_actions: string[];
    strategy_actions: string[];
  };
  collect_suggestions: CollectSuggestions;
  evidence: Record<string, unknown>;
};

export async function postResumeInsight(body: {
  resume_text?: string | null;
  career_summary?: string | null;
  category?: string | null;
}): Promise<ResumeInsight> {
  const origin = browserLargeUploadOrigin();
  const path = "/api/resume/insight";
  const url = origin ? `${origin.replace(/\/+$/, "")}${path}` : `${apiBase()}${path}`;

  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), 120_000);
  let r: Response;
  try {
    r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: ctrl.signal,
    });
  } catch (e) {
    clearTimeout(tid);
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error(
        "시장 인사이트 요청 시간이 초과되었습니다. 이력서 길이·LLM(Ollama) 기동을 확인해 주세요."
      );
    }
    throw e;
  }
  clearTimeout(tid);

  if (!r.ok) {
    let msg = `resume/insight ${r.status}`;
    const text = await r.text();
    try {
      const t = JSON.parse(text) as unknown;
      const parsed = parseFastApiDetail(t);
      if (parsed) msg = parsed;
      else if (t && typeof t === "object" && typeof (t as { error?: string }).error === "string") {
        msg = (t as { error: string }).error;
      }
    } catch {
      if (text.length && text.length < 500) msg = text;
    }
    throw new Error(msg);
  }
  return r.json() as Promise<ResumeInsight>;
}

// --- 컨설턴트(학생 다인 관리) ---

export type ConsultantStudent = {
  id: number;
  display_name: string;
  email: string | null;
  phone: string | null;
  school: string | null;
  memo: string | null;
  resume_text: string | null;
  career_summary: string | null;
  target_category: string;
  final_goal_progress: number;
  created_at: string;
  updated_at: string | null;
};

export type ConsultantCalendarEvent = {
  id: number;
  student_id: number;
  student_name: string;
  title: string;
  event_type: string;
  starts_at: string;
  ends_at: string | null;
  company_name: string | null;
  job_id: number | null;
  notes: string | null;
};

export type ConsultantMonthlyGoal = {
  id: number;
  student_id: number;
  year_month: string;
  certifications: string;
  competencies: string;
  application_areas: string;
};

export type ConsultantDashboard = {
  year: number;
  month: number;
  year_month: string;
  students: ConsultantStudent[];
  events: ConsultantCalendarEvent[];
  monthly_goals: ConsultantMonthlyGoal[];
};

export type ConsultantEligibleJob = {
  job_id: number;
  title: string;
  company: string;
  category: string;
  match_score: number;
  matched_skills: string[];
  requirements_mismatch: string[];
};

export type ConsultantStudentTargetCompany = {
  id: number;
  student_id: number;
  company_name: string;
  notes: string | null;
  priority: number;
};

export type ConsultantStudentDetail = {
  student: ConsultantStudent;
  appeal_points: string[];
  improvement_points: string[];
  preparation_notes: string[];
  target_companies: ConsultantStudentTargetCompany[];
  eligible_jobs: ConsultantEligibleJob[];
  target_aligned_jobs: ConsultantEligibleJob[];
  personal_events: ConsultantCalendarEvent[];
  current_month_goal: ConsultantMonthlyGoal | null;
};

export async function getConsultantDashboard(year: number, month: number): Promise<ConsultantDashboard> {
  const r = await fetch(
    `${browserBackendApiPath("/api/consultant/dashboard")}?year=${year}&month=${month}`,
    { cache: "no-store" }
  );
  if (!r.ok) throw new Error(`consultant/dashboard ${r.status}`);
  return r.json() as Promise<ConsultantDashboard>;
}

export async function createConsultantStudent(body: {
  display_name: string;
  target_category?: string;
  resume_text?: string | null;
  career_summary?: string | null;
}): Promise<ConsultantStudent> {
  const r = await fetch(browserBackendApiPath("/api/consultant/students"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`consultant/students POST ${r.status}`);
  return r.json() as Promise<ConsultantStudent>;
}

export async function putConsultantMonthlyGoal(
  studentId: number,
  yearMonth: string,
  body: { certifications: string; competencies: string; application_areas: string }
): Promise<ConsultantMonthlyGoal> {
  const r = await fetch(
    browserBackendApiPath(`/api/consultant/students/${studentId}/goals/${yearMonth}`),
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    }
  );
  if (!r.ok) throw new Error(`consultant/goals ${r.status}`);
  return r.json() as Promise<ConsultantMonthlyGoal>;
}

export async function postConsultantStudentEvent(
  studentId: number,
  body: {
    title: string;
    event_type: "exam" | "application_deadline" | "interview" | "other";
    starts_at: string;
    ends_at?: string | null;
    company_name?: string | null;
    job_id?: number | null;
    notes?: string | null;
  }
): Promise<ConsultantCalendarEvent> {
  const r = await fetch(browserBackendApiPath(`/api/consultant/students/${studentId}/events`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`consultant/events ${r.status}`);
  return r.json() as Promise<ConsultantCalendarEvent>;
}

export async function deleteConsultantEvent(eventId: number): Promise<void> {
  const r = await fetch(browserBackendApiPath(`/api/consultant/events/${eventId}`), {
    method: "DELETE",
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`consultant/events DELETE ${r.status}`);
}

export async function getConsultantStudentDetail(studentId: number): Promise<ConsultantStudentDetail> {
  const r = await fetch(browserBackendApiPath(`/api/consultant/students/${studentId}/detail`), {
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`consultant/detail ${r.status}`);
  return r.json() as Promise<ConsultantStudentDetail>;
}

export async function patchConsultantStudent(
  studentId: number,
  body: Partial<{
    display_name: string;
    email: string | null;
    phone: string | null;
    school: string | null;
    memo: string | null;
    resume_text: string | null;
    career_summary: string | null;
    target_category: string;
    final_goal_progress: number;
  }>
): Promise<ConsultantStudent> {
  const r = await fetch(browserBackendApiPath(`/api/consultant/students/${studentId}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`consultant/student PATCH ${r.status}`);
  return r.json() as Promise<ConsultantStudent>;
}

export async function postConsultantTargetCompany(
  studentId: number,
  body: { company_name: string; notes?: string | null; priority?: number }
): Promise<ConsultantStudentTargetCompany> {
  const r = await fetch(
    browserBackendApiPath(`/api/consultant/students/${studentId}/target-companies`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    }
  );
  if (!r.ok) throw new Error(`consultant/target-company ${r.status}`);
  return r.json() as Promise<ConsultantStudentTargetCompany>;
}

export async function deleteConsultantTargetCompany(companyId: number): Promise<void> {
  const r = await fetch(browserBackendApiPath(`/api/consultant/target-companies/${companyId}`), {
    method: "DELETE",
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`consultant/target-company DELETE ${r.status}`);
}

export type ConsultantCategoryItem = {
  slug: string;
  label: string;
  is_builtin: boolean;
  id: number | null;
};

export async function getConsultantCategories(): Promise<ConsultantCategoryItem[]> {
  const r = await fetch(browserBackendApiPath("/api/consultant/categories"), { cache: "no-store" });
  if (!r.ok) throw new Error(`consultant/categories ${r.status}`);
  return r.json() as Promise<ConsultantCategoryItem[]>;
}

export async function postConsultantCategory(body: {
  slug: string;
  label_ko: string;
}): Promise<ConsultantCategoryItem> {
  const r = await fetch(browserBackendApiPath("/api/consultant/categories"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`consultant/categories POST ${r.status}`);
  return r.json() as Promise<ConsultantCategoryItem>;
}

export async function deleteConsultantCategory(categoryId: number): Promise<void> {
  const r = await fetch(browserBackendApiPath(`/api/consultant/categories/${categoryId}`), {
    method: "DELETE",
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`consultant/categories DELETE ${r.status}`);
}

export async function deleteConsultantStudent(studentId: number): Promise<void> {
  const r = await fetch(browserBackendApiPath(`/api/consultant/students/${studentId}`), {
    method: "DELETE",
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`consultant/students DELETE ${r.status}`);
}

/** 백엔드 `X-Consultant-Import-Llm` 헤더 값 */
export type ConsultantImportLlmHeader =
  | "off"
  | "empty_input"
  | "no_model_response"
  | "bad_json"
  | "ok";

export function consultantImportLlmHint(status: string | null): string | null {
  if (!status || status === "ok") return null;
  if (status === "off")
    return "가져오기 LLM이 꺼져 있습니다(CONSULTANT_IMPORT_LLM=false). 백엔드 .env를 확인하세요.";
  if (status === "empty_input") return "가져올 이력·경력 텍스트가 비어 있어 LLM을 건너뛰었습니다.";
  if (status === "no_model_response")
    return "LLM에 연결되지 않았습니다. OPENAI_API_KEY를 넣거나 Ollama를 실행(OLLAMA_BASE_URL, OLLAMA_MODEL)한 뒤 백엔드를 재시작하세요.";
  if (status === "bad_json")
    return "LLM은 응답했지만 JSON 형식이 아니어서 필드 정리에 실패했습니다. 모델을 바꾸거나 OpenAI JSON 모드를 쓰려면 API 키를 설정하세요.";
  return `LLM 상태: ${status}`;
}

export async function postImportFromApplicantProfile(body?: {
  student_id?: number | null;
  display_name_for_new?: string | null;
}): Promise<{ student: ConsultantStudent; importLlmStatus: ConsultantImportLlmHeader | null }> {
  const url = browserBackendApiPath("/api/consultant/import-from-applicant-profile");
  let r: Response;
  try {
    r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
      cache: "no-store",
    });
  } catch (e) {
    const hint =
      e instanceof TypeError
        ? `브라우저가 ${url} 에 연결하지 못했습니다. 백엔드(uvicorn)가 http://127.0.0.1:8000 에서 실행 중인지, 방화벽·VPN을 확인하세요.`
        : e instanceof Error
          ? e.message
          : String(e);
    throw new Error(`가져오기 네트워크 오류: ${hint}`);
  }
  const importLlmStatus = r.headers.get("X-Consultant-Import-Llm") as ConsultantImportLlmHeader | null;
  if (!r.ok) {
    let msg = `가져오기 실패 (HTTP ${r.status})`;
    const ct = r.headers.get("content-type") ?? "";
    try {
      if (ct.includes("application/json")) {
        const t = (await r.json()) as { detail?: string | Record<string, unknown> };
        const d = t?.detail;
        if (typeof d === "string") msg = d;
        else if (d && typeof d === "object" && typeof d.message === "string") {
          msg = d.message;
          if (typeof d.student_id === "number") {
            msg += ` (학생 ID ${d.student_id}${typeof d.display_name === "string" ? ` · ${d.display_name}` : ""})`;
          }
        }
      } else {
        const text = (await r.text()).trim();
        if (text) msg = text.length > 280 ? `${text.slice(0, 280)}…` : text;
      }
    } catch {
      /* 본문 없음 */
    }
    throw new Error(msg);
  }
  const student = (await r.json()) as ConsultantStudent;
  return { student, importLlmStatus };
}
