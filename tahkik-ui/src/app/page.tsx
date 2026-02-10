"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Project {
  id: string;
  name: string;
  created_at?: string;
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    fetch("http://localhost:8000/api/projects")
      .then((res) => res.json())
      .then((data) => {
        setProjects(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Proje listesi alınamadı:", err);
        setLoading(false);
      });
  }, []);

  const handleCreateProject = async () => {
    const name = window.prompt("Yeni proje adı:");
    if (!name) return;

    try {
      const res = await fetch("http://localhost:8000/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });

      if (!res.ok) throw new Error("Proje oluşturulamadı");

      const newProject = await res.json();
      // Yönlendir -> Panel Ekranına (Process)
      router.push(`/projects/${newProject.id}/process`);
    } catch (err) {
      alert("Hata: " + err);
    }
  };

  const handleDeleteProject = async (id: string, e: React.MouseEvent) => {
    e.preventDefault(); // Link tıklamasını engelle
    if (!confirm("Bu projeyi silmek istediğinize emin misiniz? Bu işlem geri alınamaz!")) return;

    try {
      const res = await fetch(`http://localhost:8000/api/projects/${id}`, {
        method: "DELETE",
      });

      if (!res.ok) throw new Error("Proje silinemedi");

      setProjects((prev) => prev.filter((p) => p.id !== id));
      alert("Proje başarıyla silindi.");
    } catch (err) {
      alert("Silme işlemi başarısız: " + err);
    }
  };

  if (loading) return <div className="p-10">Yükleniyor...</div>;

  return (
    <main className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">Projelerim</h1>
          <button
            onClick={handleCreateProject}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition"
          >
            + Yeni Proje
          </button>
        </div>

        {projects.length === 0 ? (
          <div className="text-center py-20 bg-white rounded shadow text-gray-500">
            Henüz hiç proje yok. Yeni bir tane oluşturun!
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((p) => (
              <div key={p.id} className="bg-white p-6 rounded shadow hover:shadow-lg transition relative group">
                <div className="flex justify-between items-start mb-2">
                  <h2 className="text-xl font-semibold">{p.name}</h2>
                  <button
                    onClick={(e) => handleDeleteProject(p.id, e)}
                    className="text-red-400 hover:text-red-600 p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Projeyi Sil"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                    </svg>
                  </button>
                </div>
                <p className="text-xs text-gray-400 mb-4 break-all">ID: {p.id}</p>
                <div className="flex gap-2">
                  <Link
                    href={`/projects/${p.id}/editor`}
                    className="flex-1 block text-center bg-gray-100 text-gray-700 py-2 rounded hover:bg-gray-200"
                  >
                    Editör
                  </Link>
                  <Link
                    href={`/projects/${p.id}/process`}
                    className="flex-1 block text-center border border-gray-300 text-gray-600 py-2 rounded hover:bg-gray-50"
                  >
                    Panel
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
