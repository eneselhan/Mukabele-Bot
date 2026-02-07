"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Play, CheckCircle, Loader2, ArrowRight, Activity, FileText } from "lucide-react";

export default function ProcessHub() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.id as string;

    // Nüsha Durumları (Mockup: Gerçekte API'den status çekilmeli)
    const [status, setStatus] = useState<any>({});
    const [globalStatus, setGlobalStatus] = useState<any>({ busy: false, message: "Hazır", progress: 0 });

    // Durum Takibi (Polling)
    useEffect(() => {
        const interval = setInterval(() => {
            if (!projectId) return;
            fetch(`http://localhost:8000/api/projects/${projectId}/status`)
                .then(res => res.json())
                .then(data => {
                    setGlobalStatus(data);
                    // Eğer işlem bittiyse ilgili nüshanın durumunu 'done' yap (Basit mantık)
                    if (data.step === 'done' && data.nusha_index) {
                        setStatus((prev: any) => ({ ...prev, [data.nusha_index]: 'done' }));
                    }
                })
                .catch(() => { });
        }, 1000);
        return () => clearInterval(interval);
    }, [projectId]);

    const runPipeline = async (nushaIndex: number) => {
        if (globalStatus.busy) return alert("Şu an başka bir işlem yapılıyor, lütfen bekleyin.");

        try {
            await fetch(`http://localhost:8000/api/projects/${projectId}/process`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ step: 'ocr', nusha_index: nushaIndex })
            });
            // UI'da hemen loading göster
            setStatus((prev: any) => ({ ...prev, [nushaIndex]: 'processing' }));
        } catch (e) {
            alert("Başlatılamadı");
        }
    };

    const runAlignment = async () => {
        if (globalStatus.busy) return;
        try {
            await fetch(`http://localhost:8000/api/projects/${projectId}/process`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ step: 'align' }) // Hizalama adımı
            });
        } catch (e) { alert("Hizalama Başlatılamadı"); }
    };

    return (
        <div className="min-h-screen bg-slate-50 p-8 font-sans">
            <div className="max-w-6xl mx-auto">

                {/* HEADER */}
                <div className="mb-10 flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-2">
                            <Activity className="text-blue-600" /> İşlem Merkezi
                        </h1>
                        <p className="text-slate-500">Nüshaları analiz edin ve metinle hizalayın.</p>
                    </div>

                    {/* GLOBAL DURUM BAR */}
                    {globalStatus.busy && (
                        <div className="bg-white px-6 py-3 rounded-full shadow-lg border border-blue-100 flex items-center gap-4 animate-pulse">
                            <Loader2 className="animate-spin text-blue-600" />
                            <div>
                                <div className="text-xs font-bold text-blue-600 uppercase">İşleniyor</div>
                                <div className="text-sm text-slate-700">{globalStatus.message}</div>
                            </div>
                        </div>
                    )}
                </div>

                {/* NÜSHA KARTLARI */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
                    {[1, 2, 3, 4].map((n) => (
                        <div key={n} className={`bg-white rounded-xl p-6 border-2 transition-all relative overflow-hidden ${status[n] === 'done' ? 'border-green-500 shadow-green-100' :
                                status[n] === 'processing' ? 'border-blue-400 shadow-lg scale-105' : 'border-gray-100 hover:border-blue-200'
                            }`}>
                            <div className="flex justify-between items-start mb-4">
                                <div className="bg-slate-100 text-slate-600 font-bold px-3 py-1 rounded text-xs">Nüsha #{n}</div>
                                {status[n] === 'done' && <CheckCircle className="text-green-500" size={20} />}
                            </div>

                            <h3 className="font-bold text-lg mb-4 text-slate-800">Metin Analizi</h3>

                            {status[n] === 'processing' ? (
                                <div className="space-y-2">
                                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                        <div className="h-full bg-blue-500 animate-progress" style={{ width: `${globalStatus.progress}%` }}></div>
                                    </div>
                                    <p className="text-xs text-blue-500 text-center font-bold">Analiz Ediliyor...</p>
                                </div>
                            ) : status[n] === 'done' ? (
                                <div className="text-green-600 text-sm font-bold bg-green-50 p-3 rounded text-center">
                                    Tamamlandı
                                </div>
                            ) : (
                                <button
                                    onClick={() => runPipeline(n)}
                                    disabled={globalStatus.busy}
                                    className="w-full py-3 bg-slate-800 hover:bg-slate-900 text-white rounded-lg font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                                >
                                    <Play size={16} /> Başlat
                                </button>
                            )}
                        </div>
                    ))}
                </div>

                {/* ALT PANEL: HİZALAMA */}
                <div className="bg-white rounded-2xl p-8 border border-gray-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-6">
                    <div>
                        <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                            <FileText className="text-purple-600" /> Hizalama ve Sonuç
                        </h2>
                        <p className="text-slate-500 text-sm mt-1">
                            Tüm analizler bittiğinde, Word dosyası ile PDF'leri satır satır eşleştirin.
                        </p>
                    </div>

                    <div className="flex gap-4">
                        <button
                            onClick={runAlignment}
                            disabled={globalStatus.busy}
                            className="px-8 py-4 bg-purple-600 hover:bg-purple-700 text-white font-bold rounded-xl shadow-lg shadow-purple-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            <Activity size={20} /> Hizalamayı Çalıştır
                        </button>

                        <button
                            onClick={() => router.push(`/projects/${projectId}/editor`)}
                            className="px-8 py-4 bg-gray-100 hover:bg-gray-200 text-slate-700 font-bold rounded-xl transition-all flex items-center gap-2"
                        >
                            Editöre Git <ArrowRight size={20} />
                        </button>
                    </div>
                </div>

            </div>
        </div>
    );
}
