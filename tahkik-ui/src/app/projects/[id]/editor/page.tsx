"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation"; // New import for dynamic params

interface BestMatch {
    raw: string;
    score: number;
}

interface LineData {
    line_no: number;
    line_image: string;
    ocr_text: string;
    best?: BestMatch;
}

export default function EditorPage() {
    const params = useParams();
    const projectId = params.id as string;

    const [data, setData] = useState<LineData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!projectId) return;

        // Use new API endpoint for project data
        // TODO: The backend needs an endpoint to serve alignment.json content.
        // Spec says: fetch from '/api/projects/{id}/data' or similar. 
        // I will assume GET /api/projects/{id}/data returns the alignment json.
        // But currently I haven't implemented that specific endpoint in api_server.py.
        // Wait, the user prompt said: "Şimdilik URL'yi güncellemen yeterli". 
        // I should probably point to where the file is STATICALLY serving if possible, 
        // or better, I should have an endpoint. 
        // In api_server.py, I mounted `PROJECTS_DIR` to `/media`. 
        // So `alignment.json` is at `/media/{projectId}/nusha_1/alignment.json`.

        // Let's use the static path for now as it's the easiest migration step based on previous architecture.
        const url = `http://localhost:8000/media/${projectId}/nusha_1/alignment.json`;

        fetch(url)
            .then((res) => {
                if (!res.ok) throw new Error("Alignment verisi bulunamadı (Henüz işlenmemiş olabilir)");
                return res.json();
            })
            .then((jsonData) => {
                let listToUse: LineData[] = [];
                if (jsonData.aligned && Array.isArray(jsonData.aligned)) {
                    listToUse = jsonData.aligned;
                } else if (Array.isArray(jsonData)) {
                    listToUse = jsonData;
                }
                const sortedData = listToUse.sort((a, b) => (a.line_no || 0) - (b.line_no || 0));
                setData(sortedData);
                setLoading(false);
            })
            .catch((err) => {
                console.error("Veri Hatası:", err);
                setError(err.message);
                setLoading(false);
            });
    }, [projectId]);

    const getImageUrl = (fullPath: string) => {
        if (!fullPath) return "/placeholder.png";
        const filename = fullPath.split(/[/\\]/).pop();
        // Image serving also changes. 
        // It used to be /output_lines/lines/{filename}. 
        // Now images are in projects/{id}/nusha_1/lines/{filename}.
        // Mounted at /media/{id}/nusha_1/lines/{filename}
        return `http://localhost:8000/media/${projectId}/nusha_1/lines/${filename}`;
    };

    if (loading) return <div className="p-10 text-center">Editör Hazırlanıyor... (Proje: {projectId})</div>;
    if (error) return <div className="p-10 text-center text-red-500">Hata: {error}</div>;

    return (
        <main className="min-h-screen bg-gray-50 p-8">
            <div className="space-y-6 max-w-5xl mx-auto pb-20">
                <h1 className="text-2xl font-bold mb-4">Proje Editörü: {projectId}</h1>
                {data.map((item, index) => (
                    <div key={index} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col gap-4 p-4 mb-4">
                        <div className="flex justify-between items-start border-b pb-2">
                            <span className="font-bold text-gray-700">Satır #{item.line_no}</span>
                            <span className="text-xs text-gray-400">{item.line_image.split(/[/\\]/).pop()}</span>
                        </div>
                        <div className="flex flex-col md:flex-row gap-4">
                            <div className="w-full md:w-1/3 border border-gray-300 bg-gray-50 rounded p-2 flex items-center justify-center">
                                <img
                                    src={getImageUrl(item.line_image)}
                                    alt={`Satır ${index + 1}`}
                                    className="max-h-32 object-contain"
                                    crossOrigin="anonymous"
                                />
                            </div>
                            <div className="flex-1">
                                <label className="text-xs font-bold text-red-500 block mb-1">OCR (Ham):</label>
                                <div className="p-2 bg-red-50 border border-red-200 rounded text-right text-sm text-gray-700 font-arabic leading-loose h-full">
                                    {item.ocr_text || "OCR Okuyamadı"}
                                </div>
                            </div>
                            <div className="flex-1">
                                <label className="text-xs font-bold text-blue-600 block mb-1">Hizalanmış (Düzenle):</label>
                                <textarea
                                    className="w-full h-full p-2 border-2 border-blue-100 rounded focus:border-blue-500 outline-none text-right text-lg font-arabic leading-loose"
                                    defaultValue={item.best?.raw || ""}
                                    dir="rtl"
                                />
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </main>
    );
}
