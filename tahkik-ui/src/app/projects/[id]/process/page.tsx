"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { UploadCloud, FileText, Play, RefreshCw, Trash2, Check, X, Edit2, CheckSquare, CheckCircle, AlertCircle, BookOpen, ChevronDown, ChevronUp } from "lucide-react";
import Navbar from "@/components/Navbar";

// Mesajları İnsanileştirme
const humanizeMessage = (msg: string) => {
    if (!msg) return "";
    if (msg.includes("OCR")) return "Metin Okunuyor (OCR)...";
    if (msg.includes("Alignment")) return "Metin Hizalanıyor...";
    if (msg.includes("Segmentation")) return "Analiz Ediliyor (Segmentasyon)...";
    if (msg.includes("PDF ->")) return "PDF Ayrıştırılıyor...";
    if (msg.includes("success")) return "İşlem Başarılı";
    return msg;
};

export default function CompactListDashboard() {
    const params = useParams();
    const projectId = params.id as string;
    const [status, setStatus] = useState<any>(null);
    const [uploading, setUploading] = useState<string | null>(null);
    const [processing, setProcessing] = useState<string | null>(null);
    const [editingName, setEditingName] = useState<{ index: number, val: string } | null>(null);
    const [dpiSelections, setDpiSelections] = useState<Record<number, number>>({});
    const [pipelineStatuses, setPipelineStatuses] = useState<Record<number, any>>({});
    const [expandedPipelines, setExpandedPipelines] = useState<Record<number, boolean>>({});

    // Sürekli Durum Kontrolü (Polling)
    const fetchStatus = async () => {
        try {
            const res = await fetch(`http://localhost:8000/api/projects/${projectId}/status`);
            const data = await res.json();
            setStatus(data);
        } catch (e) { console.error(e); }
    };

    // Fetch pipeline status for all nushas
    const fetchPipelineStatus = async () => {
        for (let n = 1; n <= 4; n++) {
            try {
                const res = await fetch(`http://localhost:8000/api/projects/${projectId}/nusha/${n}/pipeline/status`);
                const data = await res.json();
                setPipelineStatuses(prev => ({ ...prev, [n]: data }));
            } catch (e) { console.error(`Pipeline status error for nusha ${n}:`, e); }
        }
    };

    useEffect(() => {
        fetchStatus();
        fetchPipelineStatus();
        const interval = setInterval(() => {
            fetchStatus();
            fetchPipelineStatus();
        }, 2000);
        return () => clearInterval(interval);
    }, [projectId]);

    // Dosya Yükleme
    const handleUpload = async (file: File, type: 'docx' | 'pdf', nushaIndex: number, key: string) => {
        if (!file) return;
        setUploading(key);
        const formData = new FormData();
        formData.append("file", file);
        formData.append("file_type", type);
        formData.append("nusha_index", nushaIndex.toString());

        try {
            await fetch(`http://localhost:8000/api/projects/${projectId}/upload`, { method: "POST", body: formData });
            await fetchStatus();
        } catch (e) { alert("Yükleme Hatası"); }
        finally { setUploading(null); }
    };

    // İşlem Başlatma (Unified)
    const runProcess = async (step: 'full' | 'spellcheck', nushaIndex: number | null = null) => {
        // Spellcheck - DISABLED via User Request
        // if (step === 'spellcheck') { ... }

        if (nushaIndex === null) return;

        const key = `full-${nushaIndex}`;
        const selectedDpi = dpiSelections[nushaIndex] || 300;

        setProcessing(key);
        try {
            await fetch(`http://localhost:8000/api/projects/${projectId}/process`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    step: 'full',
                    nusha_index: nushaIndex,
                    dpi: selectedDpi
                })
            });
        } catch (e) { alert("Başlatılamadı"); }
        finally { setProcessing(null); }
    };

    // Execute individual pipeline step
    const runPipelineStep = async (step: string, nushaIndex: number) => {
        const key = `${step}-${nushaIndex}`;
        setProcessing(key);
        const selectedDpi = dpiSelections[nushaIndex] || 300;

        try {
            await fetch(`http://localhost:8000/api/projects/${projectId}/nusha/${nushaIndex}/pipeline/${step}?dpi=${selectedDpi}`, {
                method: "POST"
            });
        } catch (e) {
            alert("Başlatılamadı");
        } finally {
            setProcessing(null);
            await fetchPipelineStatus();
        }
    };

    // Delete individual pipeline step
    const deletePipelineStep = async (step: string, nushaIndex: number, shouldRestart: boolean = false) => {
        const actionText = shouldRestart ? "silip tekrar başlatmak" : "silmek";
        if (!confirm(`${step.toUpperCase()} adımını ${actionText} istediğinize emin misiniz?`)) return;

        try {
            await fetch(`http://localhost:8000/api/projects/${projectId}/nusha/${nushaIndex}/pipeline/${step}`, {
                method: "DELETE"
            });
            await fetchPipelineStatus();

            if (shouldRestart) {
                // Wait a bit ensuring backend processed deletion (though await above handles it)
                await runPipelineStep(step, nushaIndex);
            }
        } catch (e) {
            alert("İşlem Başarısız");
        }
    };

    // Nüsha İsmi Kaydetme
    const saveName = async (n: number, newName: string) => {
        try {
            await fetch(`http://localhost:8000/api/projects/${projectId}/nusha/${n}/name`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: newName })
            });
            setEditingName(null);
            fetchStatus();
        } catch (e) { alert("İsim Güncellenemedi"); }
    };

    // Dosya Silme
    const handleDelete = async (type: 'docx' | 'pdf', nushaIndex: number) => {
        if (!confirm("Bu dosyayı silmek istediğinize emin misiniz?")) return;
        try {
            await fetch(`http://localhost:8000/api/projects/${projectId}/files?file_type=${type}&nusha_index=${nushaIndex}`, {
                method: "DELETE"
            });
            fetchStatus();
        } catch (e) { alert("Silme Başarısız"); }
    };

    if (!status) return <div className="p-10 text-center flex items-center justify-center gap-2 text-slate-500"><RefreshCw className="animate-spin" size={20} /> Yükleniyor...</div>;

    return (
        <>
            <Navbar />
            <div className="min-h-screen bg-slate-50 p-4 font-sans text-slate-800">
                <div className="max-w-5xl mx-auto">
                    <div className="flex justify-between items-center mb-6">
                        <h1 className="text-xl font-bold text-slate-700">Proje Kontrol Paneli</h1>
                        <a href={`/projects/${projectId}/editor`} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-bold text-sm shadow-sm transition-colors flex items-center gap-2">
                            Mukabele Görünümü <Play size={16} fill="currentColor" />
                        </a>
                    </div>

                    {/* --- 1. REFERANS METİN (YATAY BAR) --- */}
                    <div className="bg-white border border-slate-200 rounded-lg shadow-sm p-3 mb-6 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-full ${status.has_tahkik ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-400'}`}>
                                <FileText size={20} />
                            </div>
                            <div>
                                <h2 className="text-sm font-bold text-slate-700">Referans Metin (Word)</h2>
                                <p className="text-xs text-slate-500">
                                    {status.has_tahkik ? (
                                        <span className="text-green-600 font-medium flex items-center gap-1">
                                            <CheckCircle size={10} /> tahkik.docx Hazır

                                            {/* Change File Option (Text-based) */}
                                            <label className="text-[10px] text-blue-500 hover:text-blue-700 hover:underline cursor-pointer ml-2 flex items-center gap-0.5">
                                                {uploading === 'ref' ? <RefreshCw className="animate-spin" size={10} /> : <RefreshCw size={10} />}
                                                Değiştir
                                                <input type="file" className="hidden" accept=".docx" onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0], 'docx', 1, 'ref')} />
                                            </label>
                                        </span>
                                    ) : "Henüz dosya yüklenmedi"}
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            {status.has_tahkik && (
                                <span className="text-xs text-green-600 font-bold flex items-center gap-1 bg-green-50 px-2 py-1 rounded">
                                    <CheckSquare size={14} /> Word Dosyası Hazır
                                </span>
                            )}

                            {!status.has_tahkik && (
                                <label className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 border border-blue-200 text-blue-600 hover:bg-blue-100 rounded text-xs font-bold transition-colors cursor-pointer">
                                    {uploading === 'ref' ? <RefreshCw className="animate-spin" size={14} /> : <UploadCloud size={14} />}
                                    Word Yükle
                                    <input type="file" className="hidden" accept=".docx" onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0], 'docx', 1, 'ref')} />
                                </label>
                            )}

                            {status.has_tahkik && (
                                <button onClick={() => handleDelete('docx', 1)} className="p-1.5 text-slate-400 hover:text-red-500 transition-colors" title="Sil">
                                    <Trash2 size={16} />
                                </button>
                            )}
                        </div>
                    </div>


                    {/* --- 2. NÜSHALAR (LİSTE GÖRÜNÜMÜ) --- */}
                    <h2 className="text-sm font-bold text-slate-600 mb-2 uppercase tracking-wide">Mevcut Nüshalar</h2>
                    <div className="space-y-2">
                        {[1, 2, 3, 4].map(n => {
                            const nusha = status.nushas[`nusha_${n}`];
                            const isUploaded = nusha?.uploaded;
                            const isProcessing = nusha.progress?.status === 'processing' || processing === `full-${n}`;
                            const isFailed = nusha.progress?.status === 'failed';
                            const isCompleted = nusha.progress?.status === 'completed';
                            const currentDpi = dpiSelections[n] || 300;

                            return (
                                <div key={n} className={`bg-white border rounded-lg p-3 shadow-sm transition-all
                                ${isUploaded ? 'border-slate-200' : 'border-slate-100 bg-slate-50 opacity-70'}
                                ${isProcessing ? 'border-blue-300 ring-1 ring-blue-100' : ''}
                            `}>
                                    <div className="flex items-center gap-4">
                                        {/* 1. NUMARA & İSİM */}
                                        <div className="flex items-center gap-3 w-48 shrink-0">
                                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm
                                        ${isUploaded ? 'bg-purple-100 text-purple-700' : 'bg-slate-200 text-slate-400'}
                                    `}>
                                                {n}
                                            </div>

                                            {editingName?.index === n ? (
                                                <div className="flex items-center gap-1">
                                                    <input
                                                        className="w-24 text-xs border rounded p-1"
                                                        value={editingName.val}
                                                        onChange={(e) => setEditingName({ index: n, val: e.target.value })}
                                                        autoFocus
                                                    />
                                                    <button onClick={() => saveName(n, editingName.val)} className="text-green-600"><Check size={14} /></button>
                                                    <button onClick={() => setEditingName(null)} className="text-red-500"><X size={14} /></button>
                                                </div>
                                            ) : (
                                                <div className="group flex items-center gap-2">
                                                    <span className={`text-sm font-bold truncate ${isUploaded ? 'text-slate-700' : 'text-slate-400'}`}>
                                                        {nusha.name}
                                                    </span>
                                                    <button className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-blue-500"
                                                        onClick={() => setEditingName({ index: n, val: nusha.name })}>
                                                        <Edit2 size={12} />
                                                    </button>
                                                </div>
                                            )}
                                        </div>

                                        {/* 2. DURUM & PROGRESS (ORTA) */}
                                        <div className="flex-1 flex flex-col justify-center px-4 border-l border-r border-slate-100 h-10">
                                            {!isUploaded ? (
                                                <div className="flex items-center gap-2 text-slate-400 text-xs italic">
                                                    <AlertCircle size={14} /> Dosya bekleniyor...
                                                </div>
                                            ) : isProcessing ? (
                                                /* PROGRESS BAR */
                                                <div className="w-full">
                                                    <div className="flex justify-between text-[10px] font-bold text-blue-600 mb-1">
                                                        <span>{humanizeMessage(nusha.progress?.message)}</span>
                                                        <span>%{nusha.progress?.percent || 0}</span>
                                                    </div>
                                                    <div className="w-full bg-blue-100 rounded-full h-1.5">
                                                        <div className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
                                                            style={{ width: `${nusha.progress?.percent || 0}%` }}></div>
                                                    </div>
                                                </div>
                                            ) : (
                                                /* STATUS TEXT */
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2 text-xs font-medium text-slate-600" title={nusha.filename || "source.pdf"}>
                                                        <FileText size={14} className="text-purple-400" />
                                                        <span className="truncate max-w-[150px]">{nusha.filename || "Dosya Yüklü"}</span>

                                                        {/* Change File Option */}
                                                        <label className="text-[10px] text-blue-500 hover:text-blue-700 hover:underline cursor-pointer ml-2 flex items-center gap-0.5">
                                                            <RefreshCw size={10} /> Değiştir
                                                            <input type="file" className="hidden" accept=".pdf"
                                                                onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0], 'pdf', n, `n${n}`)}
                                                            />
                                                        </label>
                                                    </div>

                                                    {isFailed && <span className="text-xs text-red-600 font-bold bg-red-50 px-2 py-0.5 rounded">Hata!</span>}
                                                    {isCompleted && <span className="text-xs text-green-600 font-bold bg-green-50 px-2 py-0.5 rounded flex items-center gap-1"><CheckCircle size={10} /> Hazır</span>}
                                                </div>
                                            )}
                                        </div>

                                        {/* 3. AKSİYONLAR (SAĞ) */}
                                        <div className="flex items-center gap-2 shrink-0 w-64 justify-end">
                                            {!isUploaded ? (
                                                <label className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-blue-50 text-slate-500 hover:text-blue-600 rounded text-xs font-bold transition-colors cursor-pointer border border-transparent hover:border-blue-200">
                                                    {uploading === `n${n}` ? <RefreshCw className="animate-spin" size={14} /> : <UploadCloud size={14} />}
                                                    PDF Yükle
                                                    <input type="file" className="hidden" accept=".pdf" onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0], 'pdf', n, `n${n}`)} />
                                                </label>
                                            ) : (
                                                <>
                                                    {!isProcessing && (
                                                        <select
                                                            className="bg-slate-50 border border-slate-200 text-xs text-slate-600 rounded px-2 py-1 outline-none h-8 cursor-pointer hover:border-blue-300 transition-colors font-medium w-20"
                                                            value={currentDpi}
                                                            onChange={(e) => setDpiSelections(prev => ({ ...prev, [n]: Number(e.target.value) }))}
                                                        >
                                                            <option value={200}>200</option>
                                                            <option value={300}>300</option>
                                                            <option value={400}>400</option>
                                                        </select>
                                                    )}

                                                    {/* PIPELINE CONTROL TOGGLE */}
                                                    <button
                                                        onClick={() => setExpandedPipelines(prev => ({ ...prev, [n]: !prev[n] }))}
                                                        disabled={!status.has_tahkik}
                                                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-bold transition-all shadow-sm h-8
                                                    ${status.has_tahkik
                                                                ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-blue-200 border border-blue-600 hover:border-blue-700'
                                                                : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'}
                                                `}
                                                        title={!status.has_tahkik ? "Önce Word Yükleyin" : "Gelişmiş Analiz Menüsü"}
                                                    >
                                                        {expandedPipelines[n] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                                        Gelişmiş Analiz
                                                    </button>

                                                    <button
                                                        onClick={() => handleDelete('pdf', n)}
                                                        disabled={isProcessing}
                                                        className="w-8 h-8 flex items-center justify-center text-slate-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                                        title="Dosyayı ve Verileri Sil"
                                                    >
                                                        <Trash2 size={16} />
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </div>

                                    {/* PIPELINE STEPS PANEL (COLLAPSIBLE) */}
                                    {isUploaded && expandedPipelines[n] && pipelineStatuses[n] && (
                                        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mt-2 space-y-2">
                                            {/* ALL-IN-ONE ACTION */}
                                            <div className="bg-indigo-50 border border-indigo-100 rounded p-2 flex items-center justify-between mb-2">
                                                <div className="flex items-center gap-2 text-indigo-700">
                                                    <span className="text-lg">🚀</span>
                                                    <div>
                                                        <div className="text-xs font-bold">Tam Otomatik Analiz</div>
                                                        <div className="text-[10px] opacity-80">PDF → OCR → Hizalama</div>
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => runProcess('full', n)}
                                                    disabled={processing === `full-${n}` || !status.has_tahkik}
                                                    className={`px-3 py-1.5 rounded text-xs font-bold text-white transition-colors flex items-center gap-1
                                                        ${processing === `full-${n}` ? 'bg-indigo-300 cursor-wait' : 'bg-indigo-600 hover:bg-indigo-700'}
                                                        ${!status.has_tahkik ? 'opacity-50 cursor-not-allowed' : ''}
                                                    `}
                                                    title={!status.has_tahkik ? "Önce Word dosyası yükleyin" : "Tüm süreci başlatır"}
                                                >
                                                    {processing === `full-${n}` ? <RefreshCw className="animate-spin" size={12} /> : <Play size={12} fill="currentColor" />}
                                                    {processing === `full-${n}` ? "Çalışıyor..." : "Hepsini Çalıştır"}
                                                </button>
                                            </div>
                                            {/* Step 1: Pages */}
                                            {(() => {
                                                const step = pipelineStatuses[n]?.steps?.pages;
                                                const isCompleted = step?.status === 'completed';
                                                const isPending = step?.status === 'pending';
                                                const isRunning = processing === `pages-${n}`;

                                                return (
                                                    <div className="bg-white border border-slate-200 rounded p-2 flex items-center justify-between">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-lg">📄</span>
                                                            <div>
                                                                <div className="text-xs font-bold text-slate-700">PDF → Görüntüler</div>
                                                                {isCompleted && <div className="text-[10px] text-green-600">✅ {step.count} sayfa</div>}
                                                                {isPending && <div className="text-[10px] text-blue-500">⏸️ Bekliyor</div>}
                                                                {isRunning && <div className="text-[10px] text-blue-600">⏳ İşleniyor...</div>}
                                                            </div>
                                                        </div>
                                                        <div className="flex gap-1">
                                                            {!isCompleted && !isRunning && (
                                                                <button
                                                                    onClick={() => runPipelineStep('pages', n)}
                                                                    className="px-2 py-1 bg-blue-500 hover:bg-blue-600 text-white rounded text-[10px] font-bold"
                                                                >
                                                                    Başlat
                                                                </button>
                                                            )}
                                                            {isCompleted && (
                                                                <button
                                                                    onClick={() => deletePipelineStep('pages', n, true)}
                                                                    className="px-2 py-1 bg-slate-200 hover:bg-red-100 text-slate-600 hover:text-red-600 rounded text-[10px] font-bold"
                                                                >
                                                                    Sil ve Tekrar Başlat
                                                                </button>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })()}

                                            {/* Step 2: OCR */}
                                            {(() => {
                                                const step = pipelineStatuses[n]?.steps?.ocr;
                                                const isCompleted = step?.status === 'completed';
                                                const isPending = step?.status === 'pending';
                                                const isNotStarted = step?.status === 'not_started';
                                                const isRunning = processing === `ocr-${n}`;

                                                return (
                                                    <div className="bg-white border border-slate-200 rounded p-2 flex items-center justify-between">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-lg">🔍</span>
                                                            <div>
                                                                <div className="text-xs font-bold text-slate-700">OCR (Metin Okuma)</div>
                                                                {isCompleted && <div className="text-[10px] text-green-600">✅ {step.count} satır</div>}
                                                                {isPending && <div className="text-[10px] text-blue-500">⏸️ Bekliyor</div>}
                                                                {isNotStarted && <div className="text-[10px] text-slate-400">⏸️ Önce PDF→Görüntüler gerekli</div>}
                                                                {isRunning && <div className="text-[10px] text-blue-600">⏳ İşleniyor...</div>}
                                                            </div>
                                                        </div>
                                                        <div className="flex gap-1">
                                                            {isPending && !isRunning && (
                                                                <button
                                                                    onClick={() => runPipelineStep('ocr', n)}
                                                                    className="px-2 py-1 bg-blue-500 hover:bg-blue-600 text-white rounded text-[10px] font-bold"
                                                                >
                                                                    Başlat
                                                                </button>
                                                            )}
                                                            {isCompleted && (
                                                                <button
                                                                    onClick={() => deletePipelineStep('ocr', n, true)}
                                                                    className="px-2 py-1 bg-slate-200 hover:bg-red-100 text-slate-600 hover:text-red-600 rounded text-[10px] font-bold"
                                                                >
                                                                    Sil ve Tekrar Başlat
                                                                </button>
                                                            )}
                                                            {isNotStarted && (
                                                                <div className="px-2 py-1 bg-slate-100 text-slate-400 rounded text-[10px] font-bold cursor-not-allowed">
                                                                    Devre Dışı
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })()}

                                            {/* Step 3: Alignment */}
                                            {(() => {
                                                const step = pipelineStatuses[n]?.steps?.alignment;
                                                const isCompleted = step?.status === 'completed';
                                                const isPending = step?.status === 'pending';
                                                const isNotStarted = step?.status === 'not_started';
                                                const requiresReference = step?.requires_reference;
                                                const isRunning = processing === `alignment-${n}`;

                                                return (
                                                    <div className="bg-white border border-slate-200 rounded p-2 flex items-center justify-between">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-lg">🔗</span>
                                                            <div>
                                                                <div className="text-xs font-bold text-slate-700">Alignment (Eşleştirme)</div>
                                                                {isCompleted && <div className="text-[10px] text-green-600">✅ Tamamlandı</div>}
                                                                {isPending && !requiresReference && <div className="text-[10px] text-blue-500">⏸️ Bekliyor</div>}
                                                                {requiresReference && <div className="text-[10px] text-orange-500">⚠️ Word dosyası gerekli</div>}
                                                                {isNotStarted && !requiresReference && <div className="text-[10px] text-slate-400">⏸️ Önce OCR gerekli</div>}
                                                                {isRunning && <div className="text-[10px] text-blue-600">⏳ İşleniyor...</div>}
                                                            </div>
                                                        </div>
                                                        <div className="flex gap-1">
                                                            {isPending && !requiresReference && !isRunning && (
                                                                <button
                                                                    onClick={() => runPipelineStep('alignment', n)}
                                                                    className="px-2 py-1 bg-blue-500 hover:bg-blue-600 text-white rounded text-[10px] font-bold"
                                                                >
                                                                    Başlat
                                                                </button>
                                                            )}
                                                            {isCompleted && (
                                                                <button
                                                                    onClick={() => deletePipelineStep('alignment', n, true)}
                                                                    className="px-2 py-1 bg-slate-200 hover:bg-red-100 text-slate-600 hover:text-red-600 rounded text-[10px] font-bold"
                                                                >
                                                                    Sil ve Tekrar Başlat
                                                                </button>
                                                            )}
                                                            {(isNotStarted || requiresReference) && (
                                                                <div className="px-2 py-1 bg-slate-100 text-slate-400 rounded text-[10px] font-bold cursor-not-allowed">
                                                                    Devre Dışı
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* MUKABELE BUTONU */}
                    <div className="mt-8 flex justify-end border-t pt-6 pb-10">
                        <button
                            onClick={() => window.location.href = `/projects/${projectId}/editor`}
                            className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-4 rounded-xl font-bold text-lg shadow-lg flex items-center gap-3 transition-transform hover:scale-105"
                        >
                            <BookOpen size={24} />
                            Mukabele Ekranına Git
                        </button>
                    </div>
                </div>
            </div >
        </>
    );
}
