"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function DemandInterestCompare({
  items,
  limit = 12,
}: {
  items: { keyword: string; demand_score: number; interest_score: number }[];
  limit?: number;
}) {
  const data = [...items]
    .sort((a, b) => b.demand_score + b.interest_score - (a.demand_score + a.interest_score))
    .slice(0, limit)
    .map((x) => ({
      name: x.keyword,
      수요: Math.round(x.demand_score),
      관심: Math.round(x.interest_score),
    }));
  return (
    <div className="h-96 w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="name"
            interval={0}
            angle={-25}
            textAnchor="end"
            height={70}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
          />
          <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
            labelStyle={{ color: "#e2e8f0" }}
          />
          <Legend />
          <Bar dataKey="수요" fill="#22c55e" radius={[2, 2, 0, 0]} />
          <Bar dataKey="관심" fill="#3b82f6" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
