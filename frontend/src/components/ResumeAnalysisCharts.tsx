"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type ChartBarRow = { skill: string; demand_index: number; resume_cover: number };
export type ChartRadarRow = {
  group_key: string;
  label_ko: string;
  resume_score: number;
  market_score: number;
};
export type ChartPieRow = { name: string; value: number };

export type ResumeChartsPayload = {
  skill_bars: ChartBarRow[];
  group_radar: ChartRadarRow[];
  strength_gap_pie: ChartPieRow[];
  gap_priority_bars: ChartBarRow[];
};

const PIE_COLORS = ["#34d399", "#fbbf24", "#64748b"];
const TOOLTIP_STYLE = {
  contentStyle: { background: "#0f172a", border: "1px solid #334155" },
  labelStyle: { color: "#e2e8f0" },
};

export function ResumeAnalysisCharts({ charts }: { charts: ResumeChartsPayload }) {
  const radarData = charts.group_radar.map((r) => ({
    subject: r.label_ko,
    이력서: r.resume_score,
    시장요구: r.market_score,
  }));

  return (
    <div className="mt-6 space-y-8 border-t border-slate-800 pt-6">
      <h3 className="text-base font-semibold text-white">시각화 — 공고 대비 역량</h3>
      <p className="text-xs text-slate-500">
        수집된 채용 공고에서 추출된 스킬 빈도와 이력서(규칙 추출) 키워드를 비교합니다. LLM이 켜져 있으면
        상단 요약 문단 품질이 좋아집니다.
      </p>

      <div className="grid gap-8 lg:grid-cols-2">
        <div>
          <h4 className="mb-2 text-sm font-medium text-slate-300">상위 스킬 — 수요 지수 vs 이력서 반영</h4>
          {charts.skill_bars.length === 0 ? (
            <p className="text-sm text-slate-500">표시할 공고 스킬 데이터가 없습니다.</p>
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer>
                <BarChart
                  data={charts.skill_bars}
                  layout="vertical"
                  margin={{ top: 4, right: 8, left: 8, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="skill"
                    width={88}
                    tick={{ fill: "#94a3b8", fontSize: 10 }}
                  />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Legend />
                  <Bar dataKey="demand_index" name="수요 지수" fill="#38bdf8" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="resume_cover" name="이력서 반영도" fill="#a78bfa" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div>
          <h4 className="mb-2 text-sm font-medium text-slate-300">강점 vs 보완 (시장 상위 12개 스킬 기준)</h4>
          {charts.strength_gap_pie.length === 0 ? (
            <p className="text-sm text-slate-500">데이터 없음</p>
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={charts.strength_gap_pie}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label={({ name, percent }) =>
                      `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                    }
                  >
                    {charts.strength_gap_pie.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip {...TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      <div>
        <h4 className="mb-2 text-sm font-medium text-slate-300">역량 그룹 — 이력서 vs 시장(스킬 언급 강도)</h4>
        {radarData.length === 0 ? (
          <p className="text-sm text-slate-500">데이터 없음</p>
        ) : (
          <div className="mx-auto h-96 w-full max-w-lg">
            <ResponsiveContainer>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                <PolarGrid stroke="#334155" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <Radar
                  name="이력서"
                  dataKey="이력서"
                  stroke="#34d399"
                  fill="#34d399"
                  fillOpacity={0.35}
                />
                <Radar
                  name="시장요구"
                  dataKey="시장요구"
                  stroke="#38bdf8"
                  fill="#38bdf8"
                  fillOpacity={0.25}
                />
                <Legend />
                <Tooltip {...TOOLTIP_STYLE} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div>
        <h4 className="mb-2 text-sm font-medium text-slate-300">보완 우선순위 (수요 높음 + 이력서 미검출)</h4>
        {charts.gap_priority_bars.length === 0 ? (
          <p className="text-sm text-slate-500">갭이 없거나 공고 데이터가 부족합니다.</p>
        ) : (
          <div className="h-80 w-full">
            <ResponsiveContainer>
              <BarChart data={charts.gap_priority_bars} margin={{ top: 8, right: 8, left: 8, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="skill"
                  tick={{ fill: "#94a3b8", fontSize: 10 }}
                  angle={-25}
                  textAnchor="end"
                  height={70}
                />
                <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="demand_index" name="수요 지수" fill="#f97316" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
