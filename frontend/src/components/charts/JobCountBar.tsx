"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const LABELS: Record<string, string> = {
  data_analyst: "데이터 분석가",
  ai_engineer: "AI 엔지니어",
  backend_developer: "백엔드 개발자",
};

export function JobCountBar({ data }: { data: Record<string, number> }) {
  const chart = Object.entries(data).map(([k, v]) => ({
    name: LABELS[k] ?? k,
    count: v,
  }));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <BarChart data={chart} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
            labelStyle={{ color: "#e2e8f0" }}
          />
          <Bar dataKey="count" fill="#38bdf8" radius={[4, 4, 0, 0]} name="공고 수" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
