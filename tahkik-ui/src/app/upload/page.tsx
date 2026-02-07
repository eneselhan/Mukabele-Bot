"use client";

import { useState, useEffect } from "react";
import { UploadCloud, FileText, CheckCircle, AlertCircle, Layers } from "lucide-react";
import { useRouter } from "next/navigation";

export default function UploadPage() {
    const router = useRouter();
    const [refFile, setRefFile] = useState<File | null>(null);
    const [pdfFile, setPdfFile] = useState<File | null>(null);
    const [status, setStatus] = useState<any>(null);

    // YENİ: Hangi nüsha olduğunu seçmek için state (Varsayılan: 1)
    const [targetNusha, setTargetNusha] = useState<number>(1);

    // Mevcut Word dosyalarını listelemek için (Opsiyonel)
    const [existingFiles, setExistingFiles] = useState<string[]>([]);

    useEffect(() => {
        // İşlem durumunu periyodik kontrol et
        const interval = setInterval(() => {
            fetch("http://localhost:8000/api/status")
                .then((res) => res.json())
                .then((data) => setStatus(data))
                .catch(() => { });
        }, 1000);

        // Mevcut dosyaları çek
        fetch("http://localhost:8000/api/files")
            .then(res => res.json())
            .then(data => setExistingFiles(data.files || []))
            .catch(() => { });

        return () => clearInterval(interval);
    }, []);

    const handleUpload = async () => {
        if (!pdfFile) return alert("Lütfen bir PDF dosyası seçin!");

        // Eğer Nüsha 1 ise Word dosyası zorunlu, değilse opsiyonel (önceki kullanılabilir)
        // Ama basitlik için her zaman Word istiyoruz veya listeden seçtirebiliriz.
        // Şimdilik Word dosyası yüklenmemişse uyarı verelim.
        if (!refFile && targetNusha === 1) return alert("Ana Nüsha için Word dosyası zorunludur!");

        const formData = new FormData();
        if (pdfFile) formData.append("file", pdfFile);
        // Word dosyasını ayrı bir endpoint ile de atabiliriz ama şimdilik process isteğinde adını yollayacağız.
        // Önce dosyaları fiziksel olarak yükleyelim

        try {
            // 1. PDF Yükle
            await fetch("http://localhost:8000/api/upload", { method: "POST", body: formData });

            // 2. Word Yükle (Eğer seçildiyse)
            if (refFile) {
                const wordData = new FormData();
                wordData.append("file", refFile);
                await fetch("http://localhost:8000/api/upload", { method: "POST", body: wordData });
            }

            // 3. İşlemi Başlat
            const processBody = {
                ref_filename: refFile ? refFile.name : existingFiles.find(f => f.endsWith(".docx")) || "",
                filename: pdfFile.name,
                target_nusha_index: targetNusha // <--- KRİTİK NOKTA
            };

            const res = await fetch("http://localhost:8000/api/process", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(processBody)
            });

            if (!res.ok) {
                const err = await res.json();
                alert("Hata: " + err.detail);
            }

        } catch (error) {
            console.error(error);
            alert("Yükleme sırasında hata oluştu.");
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
            <div className="bg-white w-full max-w-2xl rounded-2xl shadow-xl p-8">

                <h1 className="text-3xl font-bold text-gray-800 mb-2 flex items-center gap-2">
                    <UploadCloud className="text-blue-600" size={32} />
                    Dosya Yükleme Merkezi
                </h1>
                <p className="text-gray-500 mb-8">Tahkik edilecek el yazması ve Word dosyasını yükleyin.</p>

                {/* NÜSHA SEÇİCİ */}
                <div className="mb-8 p-4 bg-blue-50/50 rounded-xl border border-blue-100">
                    <label className="block text-sm font-bold text-blue-800 mb-3 flex items-center gap-2">
                        <Layers size={18} /> HEDEF NÜSHA SEÇİN
                    </label>
                    <div className="flex gap-4">
                        {[1, 2, 3].map((num) => (
                            <button
                                key={num}
                                onClick={() => setTargetNusha(num)}
                                className={`flex-1 py-3 rounded-lg border-2 font-bold transition-all ${targetNusha === num
                                        ? "border-blue-600 bg-blue-600 text-white shadow-lg scale-105"
                                        : "border-gray-200 bg-white text-gray-400 hover:border-blue-300"
                                    }`}
                            >
                                {num === 1 ? "ANA NÜSHA" : `NÜSHA ${num}`}
                            </button>
                        ))}
                    </div>
                    <p className="text-xs text-blue-400 mt-2 text-center">
                        {targetNusha === 1 ? "Ana referans dosyanız. Word belgesi ile hizalanır." :
                            `Ana nüshanın yanına eklenecek ${targetNusha}. karşılaştırma dosyası.`}
                    </p>
                </div>

                <div className="space-y-6">
                    {/* PDF Yükleme */}
                    <div className="relative group">
                        <label className="block text-sm font-medium text-gray-700 mb-1">El Yazması (PDF)</label>
                        <input
                            type="file" accept=".pdf"
                            onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 transition-all cursor-pointer border border-gray-200 rounded-lg p-2"
                        />
                    </div>

                    {/* Word Yükleme */}
                    <div className="relative group">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Tahkik Metni (Word) {targetNusha !== 1 && <span className="text-gray-400 font-normal">(Ana nüshada yüklendiyse opsiyonel)</span>}
                        </label>
                        <input
                            type="file" accept=".docx"
                            onChange={(e) => setRefFile(e.target.files?.[0] || null)}
                            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-green-50 file:text-green-700 hover:file:bg-green-100 transition-all cursor-pointer border border-gray-200 rounded-lg p-2"
                        />
                    </div>
                </div>

                {/* İlerleme Çubuğu */}
                {status?.busy && (
                    <div className="mt-8 bg-gray-100 rounded-full h-4 overflow-hidden relative">
                        <div
                            className="bg-blue-600 h-full transition-all duration-500 ease-out flex items-center justify-end pr-2"
                            style={{ width: `${status.progress}%` }}
                        >
                        </div>
                        <div className="absolute top-5 left-0 w-full text-center text-xs font-bold text-blue-600 animate-pulse">
                            {status.message}
                        </div>
                    </div>
                )}

                {/* Butonlar */}
                <div className="mt-8 flex gap-4">
                    <button
                        onClick={handleUpload}
                        disabled={status?.busy}
                        className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-bold py-4 rounded-xl shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {status?.busy ? "İşleniyor..." : "Yükle ve Analiz Et 🚀"}
                    </button>

                    {!status?.busy && (
                        <button
                            onClick={() => router.push("/")}
                            className="px-6 py-4 bg-gray-100 text-gray-600 font-bold rounded-xl hover:bg-gray-200 transition-all"
                        >
                            Editöre Git
                        </button>
                    )}
                </div>

            </div>
        </div>
    );
}
