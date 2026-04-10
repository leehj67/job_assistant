import { ConsultantStudentPage } from "@/components/consultant/ConsultantStudentPage";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const n = Number(id);
  if (!Number.isFinite(n) || n < 1) {
    return <p className="text-red-300">잘못된 학생 ID입니다.</p>;
  }
  return <ConsultantStudentPage studentId={n} />;
}
