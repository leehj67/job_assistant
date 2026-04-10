"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = ["#38bdf8", "#a78bfa", "#f472b6", "#34d399", "#fbbf24", "#fb7185"];

function mergeSeries(
  series: { keyword: string; points: { date: string; interest_score: number }[] }[]
) {
  const byDate: Record<string, Record<string, number | string>> = {};
  for (const s of series) {
    for (const p of s.points) {
      const d = p.date.slice(0, 10);
      if (!byDate[d]) byDate[d] = { date: d };
      byDate[d][s.keyword] = p.interest_score;
    }
  }
  return Object.values(byDate).sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

export function TrendLine({
  series,
}: {
  series: { keyword: string; points: { date: string; interest_score: number }[] }[];
}) {
  const data = mergeSeries(series);
  const keys = series.map((s) => s.keyword);
  return (
    <div className="h-80 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} />
          <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
            labelStyle={{ color: "#e2e8f0" }}
          />
          <Legend />
          {keys.map((k, i) => (
            <Line
              key={k}
              type="monotone"
              dataKey={k}
              stroke={COLORS[i % COLORS.length]}
              dot={false}
              strokeWidth={2}
              name={k}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
