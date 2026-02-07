"use client";
import { useState } from "react";
import { UploadCloud, FileText, CheckCircle, ArrowRight, BookOpen, FileType, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

export default function SetupPage() {
    // State: Referans + 4 Nüsha slotu
    const [refFile, setRefFile] = useState<File | null>(null);
    const [nushas, setNushas] = useState<{ [key: number]: File | null }>({ 1: null, 2: null, 3: null, 4: null });

    const [uploading, setUploading] = useState(false);
    const [status, setStatus] = useState("");
    const [processing, setProcessing] = useState(false);
    const [progress, setProgress] = useState(0);
    const [processMsg, setProcessMsg] = useState("");
    const router = useRouter();

    // Dosya Seçme Handler'ı
    const handleNushaChange = (e: React.ChangeEvent<HTMLInputElement>, nushaIndex: number) => {
        if (e.target.files && e.target.files[0]) {
            setNushas(prev => ({ ...prev, [nushaIndex]: e.target.files![0] }));
        }
    };

    const handleRefChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setRefFile(e.target.files[0]);
        }
    };

    // Tekil yükleme fonksiyonu
    const uploadSingleFile = async (file: File) => {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch("http://localhost:8000/api/upload", {
            method: "POST",
            body: formData,
        });
        if (!res.ok) throw new Error(`${file.name} yüklenemedi.`);
        return await res.json();
    };

    const startAnalysis = async () => {
        if (!refFile || !nushas[1]) {
            alert("Lütfen en az Referans Metni ve Nüsha 1'i seçiniz.");
            return;
        }

        setUploading(true);
        setStatus("Dosyalar fabrikaya taşınıyor...");
        try {
            // 1. Referans Yükle
            setStatus(`Yükleniyor: ${refFile.name}...`);
            await uploadSingleFile(refFile);
            // 2. Nüshaları Yükle (Sadece seçili olanları)
            for (let i = 1; i <= 4; i++) {
                const file = nushas[i];
                if (file) {
                    setStatus(`Yükleniyor: Nüsha ${i} (${file.name})...`);
                    await uploadSingleFile(file);
                }
            }

            setStatus("Dosyalar yüklendi. İşlem başlatılıyor...");
            setUploading(false);
            setProcessing(true);

            // 3. İşlemi Başlat (/api/process)
            await fetch("http://localhost:8000/api/process", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ref_filename: refFile.name,
                    nusha_filenames: {
                        1: nushas[1]?.name,
                        2: nushas[2]?.name,
                        3: nushas[3]?.name,
                        4: nushas[4]?.name
                    }
                })
            });

            // 4. Takip Et (Polling)
            const interval = setInterval(async () => {
                try {
                    const res = await fetch("http://localhost:8000/api/status");
                    const data = await res.json();

                    setProgress(data.progress);
                    setProcessMsg(data.message);

                    if (data.step === "done") {
                        clearInterval(interval);
                        router.push("/");
                    } else if (data.step === "error") {
                        clearInterval(interval);
                        alert("Hata oluştu: " + data.message);
                        setProcessing(false);
                    }
                } catch (err) {
                    console.error("Polling hatası:", err);
                }
            }, 1000);

        } catch (error) {
            console.error(error);
            setStatus("Yükleme hatası!");
            alert("Dosyalar yüklenirken bir sorun oluştu.");
            setUploading(false);
        }
    };

    return (
        <main className="min-h-screen bg-gray-50 flex flex-col">
            <div className="flex-1 container mx-auto max-w-4xl py-12 px-4">
                <div className="bg-white rounded-2xl shadow-xl overflow-hidden min-h-[500px] flex flex-col justify-center">
                    {processing ? (
                        <div className="p-12 text-center flex flex-col items-center justify-center animate-in fade-in zoom-in duration-500">
                            <div className="relative mb-8">
                                <div className="absolute inset-0 bg-blue-100 rounded-full animate-ping opacity-75"></div>
                                <div className="bg-blue-600 p-6 rounded-full text-white relative z-10 shadow-xl">
                                    <Loader2 size={64} className="animate-spin" />
                                </div>
                            </div>

                            <h2 className="text-3xl font-bold text-gray-800 mb-2">Analiz Ediliyor...</h2>
                            <p className="text-gray-500 mb-8 text-lg">{processMsg || "Fabrika çalışıyor, lütfen bekleyin."}</p>

                            {/* Progress Bar Container */}
                            <div className="w-full max-w-lg bg-gray-200 rounded-full h-6 overflow-hidden shadow-inner border border-gray-300">
                                <div
                                    className="bg-gradient-to-r from-blue-500 to-purple-600 h-full rounded-full transition-all duration-700 ease-out flex items-center justify-center text-xs font-bold text-white shadow"
                                    style={{ width: `${progress}%` }}
                                >
                                    {progress > 5 && `%${Math.round(progress)}`}
                                </div>
                            </div>
                            <p className="text-sm text-gray-400 mt-4">Tahkik Bot sayfaları inceliyor, OCR yapıyor ve metni hizalıyor.</p>
                        </div>
                    ) : (
                        <>
                            {/* Başlık */}
                            <div className="bg-slate-800 p-8 text-white text-center">
                                <h1 className="text-3xl font-bold mb-2">Yeni Tahkik Projesi</h1>
                                <p className="text-slate-300">Referans metni ve el yazması nüshalarını (PDF) yükleyerek süreci başlat.</p>
                            </div>
                            <div className="p-8">

                                {/* 1. BÖLÜM: REFERANS METİN (ANA ÇAPA) */}
                                <div className="mb-8">
                                    <h3 className="text-lg font-bold text-gray-700 mb-3 flex items-center gap-2">
                                        <FileText className="text-blue-600" /> Referans Metin (Dizgi)
                                    </h3>
                                    <div className={`border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center transition-all ${refFile ? "border-green-500 bg-green-50" : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"}`}>
                                        <input type="file" accept=".docx,.txt" onChange={handleRefChange} className="hidden" id="refInput" />
                                        <label htmlFor="refInput" className="cursor-pointer w-full flex items-center justify-center gap-4">
                                            {refFile ? (
                                                <><CheckCircle className="text-green-600" size={24} /><span className="font-semibold text-gray-800">{refFile.name}</span></>
                                            ) : (
                                                <><UploadCloud className="text-gray-400" size={24} /><span className="text-gray-600">Word veya TXT dosyasını buraya bırak veya seç</span></>
                                            )}
                                        </label>
                                    </div>
                                </div>
                                {/* 2. BÖLÜM: NÜSHALAR (GRID) */}
                                <h3 className="text-lg font-bold text-gray-700 mb-3 flex items-center gap-2">
                                    <BookOpen className="text-purple-600" /> El Yazması Nüshalar (PDF)
                                </h3>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {[1, 2, 3, 4].map((num) => (
                                        <div key={num} className={`relative border rounded-xl p-4 transition-all ${nushas[num] ? "border-green-500 bg-green-50 ring-1 ring-green-200" : "border-gray-200 bg-gray-50 hover:border-purple-300"}`}>
                                            <div className="flex justify-between items-center mb-2">
                                                <span className={`text-sm font-bold ${num === 1 ? "text-purple-700" : "text-gray-500"}`}>
                                                    Nüsha {num} {num === 1 && "(Asıl)"}
                                                </span>
                                                {nushas[num] && <CheckCircle size={16} className="text-green-600" />}
                                            </div>

                                            <input
                                                type="file" accept=".pdf"
                                                onChange={(e) => handleNushaChange(e, num)}
                                                className="hidden" id={`nushaInput-${num}`}
                                            />
                                            <label htmlFor={`nushaInput-${num}`} className="cursor-pointer block text-center py-4 border border-dashed border-gray-300 rounded-lg hover:bg-white transition-colors">
                                                {nushas[num] ? (
                                                    <span className="text-sm font-semibold text-gray-800 break-all px-2">{nushas[num]?.name}</span>
                                                ) : (
                                                    <span className="text-xs text-gray-400">+ PDF Ekle</span>
                                                )}
                                            </label>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            {/* Alt Bar */}
                            <div className="bg-gray-50 p-6 border-t border-gray-100 flex justify-between items-center">
                                <div className={`text-gray-500 text-sm font-medium pl-2 ${uploading ? "animate-pulse" : ""}`}>
                                    {status}
                                </div>
                                <button
                                    onClick={startAnalysis}
                                    disabled={uploading || !refFile || !nushas[1]}
                                    className={`flex items-center gap-2 px-8 py-3 rounded-xl font-bold text-white transition-all shadow-lg ${uploading || !refFile || !nushas[1] ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700 hover:shadow-blue-200 hover:-translate-y-1"}`}
                                >
                                    {uploading ? "Yükleniyor..." : "Analizi Başlat"}
                                    {!uploading && <ArrowRight size={20} />}
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </main>
    );
}
