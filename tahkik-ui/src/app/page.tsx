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
      // Yönlendir -> Setup Ekranına
      router.push(`/projects/${newProject.id}/setup`);
    } catch (err) {
      alert("Hata: " + err);
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
              <div key={p.id} className="bg-white p-6 rounded shadow hover:shadow-lg transition">
                <h2 className="text-xl font-semibold mb-2">{p.name}</h2>
                <p className="text-xs text-gray-400 mb-4 break-all">ID: {p.id}</p>
                <div className="flex gap-2">
                  <Link
                    href={`/projects/${p.id}/editor`}
                    className="flex-1 block text-center bg-gray-100 text-gray-700 py-2 rounded hover:bg-gray-200"
                  >
                    Editör
                  </Link>
                  <Link
                    href={`/projects/${p.id}/setup`}
                    className="flex-1 block text-center border border-gray-300 text-gray-600 py-2 rounded hover:bg-gray-50"
                  >
                    Ayarlar
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
