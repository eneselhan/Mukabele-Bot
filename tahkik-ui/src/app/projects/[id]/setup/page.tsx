"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { UploadCloud, FileText, CheckCircle, ArrowRight, Layers, FileType } from "lucide-react";

export default function ProjectSetup() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.id as string;

    const [project, setProject] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    // Dosya Yükleme Durumları
    const [uploading, setUploading] = useState<string | null>(null); // 'ref' or 'n1', 'n2'...
    const [uploads, setUploads] = useState<{ [key: string]: boolean }>({});

    // DPI Ayarı (Varsayılan 300)
    const [dpi, setDpi] = useState<number>(300);

    useEffect(() => {
        // Proje verisini çek
        if (!projectId) return;
        fetch(`http://localhost:8000/api/projects/${projectId}`)
            .then(res => res.json())
            .then(data => {
                setProject(data);
                setLoading(false);
                // Eğer backend dosya varlığını dönüyorsa burayı güncelle (İleride)
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, [projectId]);

    const handleUpload = async (file: File, type: 'docx' | 'pdf', nushaIndex: number = 1, key: string) => {
        if (!file) return;
        setUploading(key);

        const formData = new FormData();
        formData.append("file", file);
        formData.append("type", type);
        formData.append("nusha_index", nushaIndex.toString());
        // DPI sadece PDF yüklemelerinde anlamlı ama her ihtimale karşı gönderelim, backend filter eder.
        formData.append("dpi", dpi.toString());

        try {
            const res = await fetch(`http://localhost:8000/api/projects/${projectId}/upload`, {
                method: "POST",
                body: formData
            });

            if (res.ok) {
                setUploads(prev => ({ ...prev, [key]: true }));
            } else {
                alert("Yükleme başarısız!");
            }
        } catch (e) {
            console.error(e);
            alert("Hata oluştu.");
        } finally {
            setUploading(null);
        }
    };

    if (loading) return <div className="p-10 text-center">Proje Yükleniyor...</div>;

    return (
        <div className="min-h-screen bg-gray-50 p-8 font-sans">
            <div className="max-w-5xl mx-auto">
                {/* BAŞLIK */}
                <header className="mb-8 flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-800">{project?.name || "Proje Kurulumu"}</h1>
                        <p className="text-gray-500 text-sm mt-1">ID: {projectId}</p>
                    </div>
                    <button
                        onClick={() => router.push(`/projects/${projectId}/process`)}
                        className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-bold shadow-lg transition-all"
                    >
                        İşlem Merkezine Git <ArrowRight size={18} />
                    </button>
                </header>

                {/* AYARLAR BAR */}
                <div className="bg-blue-50 border border-blue-200 p-4 rounded-xl mb-8 flex items-center gap-4">
                    <div className="font-bold text-blue-800 flex items-center gap-2">
                        <FileType size={20} /> Görüntü Kalitesi (DPI):
                    </div>
                    <select
                        value={dpi}
                        onChange={(e) => setDpi(Number(e.target.value))}
                        className="bg-white border border-blue-300 text-gray-700 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2.5"
                    >
                        <option value={200}>200 DPI (Hızlı - Düşük Bellek)</option>
                        <option value={300}>300 DPI (Standart - Önerilen)</option>
                        <option value={400}>400 DPI (Yüksek Kalite - Yavaş)</option>
                    </select>
                    <div className="text-xs text-blue-600 ml-auto">
                        * Bu ayar, yükleyeceğiniz PDF dosyalarının görüntü kalitesini belirler.
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">

                    {/* SOL: REFERANS METİN (WORD) */}
                    <div className="md:col-span-1 space-y-6">
                        <div className={`bg-white p-6 rounded-xl border-2 transition-all ${uploads['ref'] ? 'border-green-500 shadow-green-100' : 'border-blue-100 shadow-sm'}`}>
                            <h2 className="text-lg font-bold text-gray-700 flex items-center gap-2 mb-4">
                                <FileText className="text-blue-600" /> Tahkik Metni
                            </h2>
                            <p className="text-xs text-gray-400 mb-4">Word (.docx) formatındaki ana metniniz.</p>

                            {uploads['ref'] ? (
                                <div className="bg-green-50 text-green-700 p-3 rounded-lg flex items-center gap-2 font-bold justify-center">
                                    <CheckCircle size={20} /> Yüklendi
                                </div>
                            ) : (
                                <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-blue-300 border-dashed rounded-lg cursor-pointer bg-blue-50 hover:bg-blue-100 transition-colors">
                                    <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                        {uploading === 'ref' ? (
                                            <span className="text-sm text-blue-600 font-bold animate-pulse">Yükleniyor...</span>
                                        ) : (
                                            <>
                                                <UploadCloud className="w-8 h-8 mb-2 text-blue-500" />
                                                <p className="text-sm text-gray-500"><span className="font-semibold">Word Seç</span></p>
                                            </>
                                        )}
                                    </div>
                                    <input type="file" className="hidden" accept=".docx"
                                        onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0], 'docx', 1, 'ref')}
                                        disabled={!!uploading}
                                    />
                                </label>
                            )}
                        </div>
                    </div>

                    {/* SAĞ: NÜSHALAR (PDF) */}
                    <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {[1, 2, 3, 4].map((nushaNum) => (
                            <div key={nushaNum} className={`bg-white p-5 rounded-xl border-2 relative overflow-hidden ${uploads[`n${nushaNum}`] ? 'border-purple-500' : 'border-gray-200'}`}>
                                <div className="absolute top-0 right-0 bg-gray-100 px-3 py-1 rounded-bl-lg text-xs font-bold text-gray-500">
                                    #{nushaNum}
                                </div>
                                <h3 className="font-bold text-gray-800 flex items-center gap-2 mb-1">
                                    <Layers size={18} className={nushaNum === 1 ? "text-purple-600" : "text-gray-400"} />
                                    {nushaNum === 1 ? "Ana Nüsha" : `Nüsha ${nushaNum}`}
                                </h3>
                                <p className="text-xs text-gray-400 mb-4">PDF Formatında el yazması.</p>

                                {uploads[`n${nushaNum}`] ? (
                                    <div className="flex items-center gap-2 text-purple-700 font-bold text-sm bg-purple-50 p-2 rounded">
                                        <CheckCircle size={16} /> Dosya Hazır (DPI: {dpi})
                                    </div>
                                ) : (
                                    <label className="block w-full">
                                        <span className="sr-only">Dosya seç</span>
                                        <input type="file" accept=".pdf"
                                            className="block w-full text-sm text-slate-500
                                    file:mr-4 file:py-2 file:px-4
                                    file:rounded-full file:border-0
                                    file:text-xs file:font-semibold
                                    file:bg-purple-50 file:text-purple-700
                                    hover:file:bg-purple-100 cursor-pointer"
                                            onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0], 'pdf', nushaNum, `n${nushaNum}`)}
                                            disabled={!!uploading}
                                        />
                                    </label>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
