"use client";
import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { UploadCloud, FileText, Play, RefreshCw, Trash2, Check, X, Edit2, CheckSquare, CheckCircle, AlertCircle, BookOpen, ChevronDown, ChevronUp, ChevronRight, GripVertical, Eye, ZoomIn, XCircle } from "lucide-react";
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
    const [nushaOrder, setNushaOrder] = useState<number[]>([]);
    const [draggedItem, setDraggedItem] = useState<number | null>(null);
    // Pipeline output preview state
    const [pipelineOutputs, setPipelineOutputs] = useState<Record<number, any>>({});
    const [outputPreviews, setOutputPreviews] = useState<Record<string, boolean>>({});
    const [lightboxImage, setLightboxImage] = useState<string | null>(null);
    const [expandedFunctions, setExpandedFunctions] = useState<Record<string, boolean>>({});

    // Sürekli Durum Kontrolü (Polling)
    const fetchStatus = async () => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/status`);
            const data = await res.json();
            setStatus(data);

            // Sync order: If backend has order, use it. If not, default to ID sort.
            if (data.nushas) {
                const currentIds = Object.values(data.nushas).map((n: any) => n.id).sort((a: any, b: any) => a - b);

                // If backend has a saved order, try to use it
                if (data.nusha_order && Array.isArray(data.nusha_order)) {
                    // Validasyon: Saved order must contain same IDs as current
                    const savedOrder = data.nusha_order;
                    const isValid = currentIds.every((id: number) => savedOrder.includes(id)) && savedOrder.length === currentIds.length;

                    if (isValid) {
                        setNushaOrder(savedOrder);
                    } else {
                        // Fallback or merge new items
                        // New items (in currentIds but not in savedOrder) go to end
                        const newItems = currentIds.filter((id: any) => !savedOrder.includes(id));
                        const validSaved = savedOrder.filter((id: any) => currentIds.includes(id));
                        setNushaOrder([...validSaved, ...newItems]);
                    }
                } else if (nushaOrder.length === 0) {
                    // Initial load, no saved order -> Default numeric
                    setNushaOrder(currentIds);
                } else {
                    // We have local state, check for new items from backend
                    const newItems = currentIds.filter((id: any) => !nushaOrder.includes(id));
                    if (newItems.length > 0) {
                        setNushaOrder(prev => [...prev, ...newItems]);
                    }
                }
            }

            return data;
        } catch (e) { console.error(e); return null; }
    };

    // Drag Handlers
    const handleDragStart = (e: React.DragEvent, id: number) => {
        setDraggedItem(id);
        e.dataTransfer.effectAllowed = "move";
        // Ghost image fix if needed
    };

    const handleDragOver = (e: React.DragEvent, targetId: number) => {
        e.preventDefault();
        if (draggedItem === null || draggedItem === targetId) return;

        const currentOrder = [...nushaOrder];
        const draggedIdx = currentOrder.indexOf(draggedItem);
        const targetIdx = currentOrder.indexOf(targetId);

        if (draggedIdx === -1 || targetIdx === -1) return;

        // Swap
        currentOrder.splice(draggedIdx, 1);
        currentOrder.splice(targetIdx, 0, draggedItem);

        setNushaOrder(currentOrder);
    };

    const handleDragEnd = async () => {
        setDraggedItem(null);
        // Persist order
        try {
            await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/order`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order: nushaOrder })
            });
        } catch (e) { console.error("Failed to save order", e); }
    };

    // Fetch pipeline status for all nushas
    const fetchPipelineStatus = async (currentStatus: any) => {
        if (!currentStatus?.nushas) return;
        const nushaIds = Object.values(currentStatus.nushas).map((n: any) => n.id);

        for (const n of nushaIds) {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/nusha/${n}/pipeline/status`);
                const data = await res.json();
                setPipelineStatuses(prev => ({ ...prev, [n]: data }));
            } catch (e) { console.error(`Pipeline status error for nusha ${n}:`, e); }
        }
    };

    // Fetch pipeline outputs for a specific nusha (called on demand)
    const fetchPipelineOutputs = useCallback(async (nushaIndex: number) => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/nusha/${nushaIndex}/pipeline/outputs`);
            if (res.ok) {
                const data = await res.json();
                setPipelineOutputs(prev => ({ ...prev, [nushaIndex]: data }));
            }
        } catch (e) { console.error(`Pipeline outputs error for nusha ${nushaIndex}:`, e); }
    }, [projectId]);

    // Toggle preview for a specific step
    const togglePreview = (nushaIndex: number, step: string) => {
        const key = `${nushaIndex}-${step}`;
        const isCurrentlyOpen = outputPreviews[key];
        if (!isCurrentlyOpen && !pipelineOutputs[nushaIndex]) {
            fetchPipelineOutputs(nushaIndex);
        }
        setOutputPreviews(prev => ({ ...prev, [key]: !prev[key] }));
    };

    useEffect(() => {
        const init = async () => {
            const data = await fetchStatus();
            if (data) fetchPipelineStatus(data);
        };
        init();

        const interval = setInterval(async () => {
            const data = await fetchStatus();
            if (data) fetchPipelineStatus(data);
        }, 2000);
        return () => clearInterval(interval);
    }, [projectId]);

    // --- ACTIONS ---

    const saveName = async (n: number, name: string) => {
        try {
            await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/nusha/${n}/rename`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            setEditingName(null);
            fetchStatus();
        } catch (e) { console.error(e); }
    };

    const handleUpload = async (files: FileList | null, type: string, nushaIndex: number, loadingKey: string) => {
        if (!files || files.length === 0) return;
        setUploading(loadingKey);

        const formData = new FormData();
        Array.from(files).forEach((file) => {
            formData.append('files', file);
        });
        formData.append('file_type', type);
        formData.append('nusha_index', nushaIndex.toString());

        try {
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/upload`, {
                method: 'POST',
                body: formData
            });
            if (!res.ok) throw new Error('Upload failed');
            await fetchStatus();
        } catch (e) {
            console.error(e);
            alert("Yükleme başarısız!");
        } finally {
            setUploading(null);
        }
    };

    const handleDelete = async (type: string, nushaIndex: number) => {
        if (!confirm("Bu nüşayı ve tüm verilerini silmek istediğinize emin misiniz?")) return;

        try {
            await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/files`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_type: type, nusha_index: nushaIndex })
            });
            fetchStatus();
        } catch (e) { console.error(e); }
    };

    const runProcess = async (type: string, nushaIndex: number) => {
        if (type === 'full') {
            setProcessing(`full-${nushaIndex}`);
            try {
                // Unified endpoint: pipeline/full
                await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/nusha/${nushaIndex}/pipeline/full`, {
                    method: 'POST'
                });
                setExpandedPipelines(prev => ({ ...prev, [nushaIndex]: true }));
            } catch (e) { console.error(e); }
            setTimeout(() => setProcessing(null), 2000);
        }
    };

    const runPipelineStep = async (step: string, nushaIndex: number) => {
        setProcessing(`${step}-${nushaIndex}`);
        const dpi = dpiSelections[nushaIndex] || 300;
        try {
            await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/nusha/${nushaIndex}/pipeline/${step}?dpi=${dpi}`, {
                method: 'POST'
            });
        } catch (e) { console.error(e); }
        setTimeout(() => setProcessing(null), 2000);
    };

    const deletePipelineStep = async (step: string, nushaIndex: number, restart: boolean = false) => {
        if (!confirm("Bu işlem bu aşamadaki verileri sıfırlayacak. Emin misiniz?")) return;

        try {
            await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/nusha/${nushaIndex}/pipeline/${step}`, {
                method: 'DELETE'
            });

            if (restart) {
                // Small delay to ensure deletion matches backend state
                setTimeout(() => runPipelineStep(step, nushaIndex), 500);
            } else {
                fetchStatus();
            }
        } catch (e) { console.error("Delete failed", e); }
    };

    return (
        <>
            <Navbar />

            {/* Project Header */}
            <div className="bg-white border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
                    <div className="bg-purple-100 p-2 rounded-lg text-purple-700">
                        <BookOpen size={20} />
                    </div>
                    <div>
                        <h1 className="text-lg font-bold text-slate-800 leading-tight">
                            {status?.name || "Yükleniyor..."}
                        </h1>
                        <p className="text-xs text-slate-500 flex items-center gap-1">
                            <span className="font-medium text-slate-600">Proje ID:</span> {projectId}
                        </p>
                    </div>
                </div>
            </div>

            <div className="min-h-screen bg-slate-50 pb-20 pt-6">
                <div className="max-w-4xl mx-auto p-4 space-y-8">
                    {/* --- 1. WORD DOSYASI (REFERANS METİN) --- */}
                    <div className="bg-white rounded-lg p-4 border border-indigo-100 shadow-sm">
                        <div className="flex justify-between items-center mb-2">
                            <h2 className="text-sm font-bold text-indigo-900 uppercase tracking-wide flex items-center gap-2">
                                <BookOpen size={16} />
                                Referans Metin (Word)
                            </h2>
                            {status?.has_tahkik ? (
                                <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs font-bold flex items-center gap-1">
                                    <CheckCircle size={12} /> Yüklendi
                                </span>
                            ) : (
                                <span className="bg-orange-100 text-orange-700 px-2 py-0.5 rounded text-xs font-bold flex items-center gap-1">
                                    <AlertCircle size={12} /> Bekleniyor
                                </span>
                            )}
                        </div>

                        <div className="flex items-center gap-4">
                            <div className="flex-1">
                                <p className="text-xs text-slate-500 mb-2">
                                    Tahkik yapılacak ana metni Word formatında yükleyiniz. Hizalama işlemi için gereklidir.
                                </p>
                            </div>

                            <label className={`
                                flex items-center gap-2 px-4 py-2 rounded-lg font-bold shadow-sm transition-all cursor-pointer text-xs
                                ${status?.has_tahkik
                                    ? 'bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-600'
                                    : 'bg-indigo-600 text-white hover:bg-indigo-700 ring-4 ring-indigo-50'}
                            `}>
                                {uploading === 'docx' ? <RefreshCw className="animate-spin" size={14} /> : <UploadCloud size={14} />}
                                {status?.has_tahkik ? "Word Dosyasını Güncelle" : "Word Dosyası Yükle"}
                                <input
                                    type="file"
                                    className="hidden"
                                    accept=".docx"
                                    onChange={(e) => handleUpload(e.target.files, 'docx', 1, 'docx')}
                                />
                            </label>
                        </div>
                    </div>

                    {/* --- 2. NÜSHALAR (LİSTE GÖRÜNÜMÜ) --- */}
                    <div className="flex justify-between items-center mb-2">
                        <h2 className="text-sm font-bold text-slate-600 uppercase tracking-wide">Mevcut Nüshalar</h2>
                    </div>

                    <div className="space-y-2">
                        <div className="space-y-2">
                            {nushaOrder.map((id) => {
                                const nusha = status?.nushas ? status.nushas[`nusha_${id}`] : null;
                                if (!nusha) return null;

                                const n = nusha.id;
                                const isUploaded = nusha?.uploaded;
                                const isProcessing = nusha.progress?.status === 'processing' || processing === `full-${n}`;
                                const isFailed = nusha.progress?.status === 'failed';
                                const isCompleted = nusha.progress?.status === 'completed';
                                const currentDpi = dpiSelections[n] || 300;
                                const isDragged = draggedItem === n;

                                return (
                                    <div
                                        key={n}
                                        draggable={true}
                                        onDragStart={(e) => handleDragStart(e, n)}
                                        onDragOver={(e) => handleDragOver(e, n)}
                                        onDragEnd={handleDragEnd}
                                        className={`bg-white border rounded-lg p-3 shadow-sm transition-all cursor-move
                                    ${isUploaded ? 'border-slate-200' : 'border-slate-100 bg-slate-50 opacity-70'}
                                    ${isProcessing ? 'border-blue-300 ring-1 ring-blue-100' : ''}
                                    ${isDragged ? 'opacity-50 ring-2 ring-indigo-300' : ''}
                                `}>
                                        <div className="flex items-center gap-4">
                                            {/* 1. NUMARA & İSİM */}
                                            <div className="flex items-center gap-3 w-48 shrink-0">
                                                <div className="text-slate-300 cursor-grab active:cursor-grabbing hover:text-slate-500">
                                                    <GripVertical size={16} />
                                                </div>
                                                <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm
                                        ${isUploaded ? 'bg-purple-100 text-purple-700' : 'bg-slate-200 text-slate-400'}
                                    `}>
                                                    {n}
                                                </div>

                                                {editingName?.index === n ? (
                                                    <div className="flex items-center gap-1">
                                                        <input
                                                            className="w-24 text-xs border rounded p-1"
                                                            value={editingName?.val || ''}
                                                            onChange={(e) => setEditingName({ index: n, val: e.target.value })}
                                                            autoFocus
                                                        />
                                                        <button onClick={() => saveName(n, editingName?.val || '')} className="text-green-600"><Check size={14} /></button>
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
                                                                    onChange={(e) => handleUpload(e.target.files, 'pdf', n, `n${n}`)}
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
                                                        <input type="file" className="hidden" accept=".pdf" onChange={(e) => handleUpload(e.target.files, 'pdf', n, `n${n}`)} />
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

                                        {/* PIPELINE STEPS INCLUDED HERE (Keeping existing logic inside map) */}
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
                                                    const previewKey = `${n}-pages`;
                                                    const showPreview = outputPreviews[previewKey] && isCompleted;
                                                    const outputs = pipelineOutputs[n];

                                                    return (
                                                        <div className="bg-white border border-slate-200 rounded overflow-hidden">
                                                            <div className="p-2 flex items-center justify-between">
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
                                                                    {isCompleted && (
                                                                        <button
                                                                            onClick={() => togglePreview(n, 'pages')}
                                                                            className={`px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 transition-colors ${showPreview ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 hover:bg-blue-50 text-slate-500 hover:text-blue-600'}`}
                                                                        >
                                                                            <Eye size={10} /> Önizle
                                                                        </button>
                                                                    )}
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
                                                            {/* Pages Preview — Scrollable thumbnail grid */}
                                                            {showPreview && outputs?.pages && (
                                                                <div className="border-t border-slate-100 bg-slate-50 p-2">
                                                                    <div className="overflow-x-auto">
                                                                        <div className="flex gap-2 pb-1" style={{ minWidth: 'max-content' }}>
                                                                            {outputs.pages.map((filename: string, idx: number) => (
                                                                                <div
                                                                                    key={idx}
                                                                                    className="relative group cursor-pointer flex-shrink-0"
                                                                                    onClick={() => setLightboxImage(`http://127.0.0.1:8000/media/${projectId}/nusha_${n}/pages/${filename}`)}
                                                                                >
                                                                                    <img
                                                                                        src={`http://127.0.0.1:8000/media/${projectId}/nusha_${n}/pages/${filename}`}
                                                                                        alt={filename}
                                                                                        className="h-32 w-auto rounded border border-slate-200 shadow-sm hover:shadow-md hover:border-blue-300 transition-all"
                                                                                        loading="lazy"
                                                                                    />
                                                                                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 rounded flex items-center justify-center transition-all">
                                                                                        <ZoomIn size={20} className="text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow" />
                                                                                    </div>
                                                                                    <div className="text-[9px] text-center text-slate-400 mt-0.5 truncate max-w-[80px]">{filename}</div>
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    </div>
                                                                    <div className="text-[9px] text-slate-400 mt-1">← Kaydırarak diğer sayfaları görün | Tıklayarak büyütün →</div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })()}

                                                {/* Step 2: Segmentation */}
                                                {(() => {
                                                    const step = pipelineStatuses[n]?.steps?.segmentation;
                                                    const isCompleted = step?.status === 'completed';
                                                    const isPending = step?.status === 'pending';
                                                    const isNotStarted = step?.status === 'not_started';
                                                    const isRunning = processing === `segmentation-${n}`;
                                                    const previewKey = `${n}-segmentation`;
                                                    const showPreview = outputPreviews[previewKey] && isCompleted;
                                                    const outputs = pipelineOutputs[n];

                                                    return (
                                                        <div className="bg-white border border-slate-200 rounded overflow-hidden">
                                                            <div className="p-2 flex items-center justify-between">
                                                                <div className="flex items-center gap-2">
                                                                    <span className="text-lg">✂️</span>
                                                                    <div>
                                                                        <div className="text-xs font-bold text-slate-700">Satırlara Ayırma (Segmentasyon)</div>
                                                                        {isCompleted && <div className="text-[10px] text-green-600">✅ {step.count} satır</div>}
                                                                        {isPending && <div className="text-[10px] text-blue-500">⏸️ Bekliyor</div>}
                                                                        {isNotStarted && <div className="text-[10px] text-slate-400">⏸️ Önce PDF→Görüntüler gerekli</div>}
                                                                        {isRunning && <div className="text-[10px] text-blue-600">⏳ İşleniyor...</div>}
                                                                    </div>
                                                                </div>
                                                                <div className="flex gap-1">
                                                                    {isCompleted && (
                                                                        <button
                                                                            onClick={() => togglePreview(n, 'segmentation')}
                                                                            className={`px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 transition-colors ${showPreview ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 hover:bg-blue-50 text-slate-500 hover:text-blue-600'}`}
                                                                        >
                                                                            <Eye size={10} /> Önizle
                                                                        </button>
                                                                    )}
                                                                    {isPending && !isRunning && (
                                                                        <button
                                                                            onClick={() => runPipelineStep('segmentation', n)}
                                                                            className="px-2 py-1 bg-blue-500 hover:bg-blue-600 text-white rounded text-[10px] font-bold"
                                                                        >
                                                                            Başlat
                                                                        </button>
                                                                    )}
                                                                    {isCompleted && (
                                                                        <button
                                                                            onClick={() => deletePipelineStep('segmentation', n, true)}
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
                                                            {/* Segmentation Preview — Scrollable line images */}
                                                            {showPreview && outputs?.lines && (
                                                                <div className="border-t border-slate-100 bg-slate-50 p-2">
                                                                    <div className="overflow-y-auto max-h-64 space-y-1">
                                                                        {outputs.lines.map((filename: string, idx: number) => (
                                                                            <div key={idx} className="flex items-center gap-2 bg-white rounded border border-slate-100 p-1 hover:border-blue-200 transition-colors cursor-pointer"
                                                                                onClick={() => setLightboxImage(`http://127.0.0.1:8000/media/${projectId}/nusha_${n}/lines/${filename}`)}
                                                                            >
                                                                                <span className="text-[9px] text-slate-400 w-6 text-right shrink-0">{idx + 1}</span>
                                                                                <img
                                                                                    src={`http://127.0.0.1:8000/media/${projectId}/nusha_${n}/lines/${filename}`}
                                                                                    alt={filename}
                                                                                    className="h-6 w-auto max-w-full rounded"
                                                                                    loading="lazy"
                                                                                />
                                                                                <span className="text-[8px] text-slate-300 truncate">{filename}</span>
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                    <div className="text-[9px] text-slate-400 mt-1">{outputs.lines.length} satır resmi | Tıklayarak büyütün</div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })()}

                                                {/* Step 3: Text Recognition (Google Vision) */}
                                                {(() => {
                                                    const step = pipelineStatuses[n]?.steps?.text_recognition;
                                                    const isCompleted = step?.status === 'completed';
                                                    const isPending = step?.status === 'pending';
                                                    const isNotStarted = step?.status === 'not_started';
                                                    const isRunning = processing === `text_recognition-${n}`;
                                                    const previewKey = `${n}-ocr`;
                                                    const showPreview = outputPreviews[previewKey] && isCompleted;
                                                    const outputs = pipelineOutputs[n];

                                                    return (
                                                        <div className="bg-white border border-slate-200 rounded overflow-hidden">
                                                            <div className="p-2 flex items-center justify-between">
                                                                <div className="flex items-center gap-2">
                                                                    <span className="text-lg">🔍</span>
                                                                    <div>
                                                                        <div className="text-xs font-bold text-slate-700">Google Vision ile OCR Yapma</div>
                                                                        {isCompleted && <div className="text-[10px] text-green-600">✅ {step.count} dosya</div>}
                                                                        {isPending && <div className="text-[10px] text-blue-500">⏸️ Bekliyor</div>}
                                                                        {isNotStarted && <div className="text-[10px] text-slate-400">⏸️ Önce Segmentasyon gerekli</div>}
                                                                        {isRunning && <div className="text-[10px] text-blue-600">⏳ İşleniyor...</div>}
                                                                    </div>
                                                                </div>
                                                                <div className="flex gap-1">
                                                                    {isCompleted && (
                                                                        <button
                                                                            onClick={() => togglePreview(n, 'ocr')}
                                                                            className={`px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 transition-colors ${showPreview ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 hover:bg-blue-50 text-slate-500 hover:text-blue-600'}`}
                                                                        >
                                                                            <Eye size={10} /> Önizle
                                                                        </button>
                                                                    )}
                                                                    {isPending && !isRunning && (
                                                                        <button
                                                                            onClick={() => runPipelineStep('text_recognition', n)}
                                                                            className="px-2 py-1 bg-blue-500 hover:bg-blue-600 text-white rounded text-[10px] font-bold"
                                                                        >
                                                                            Başlat
                                                                        </button>
                                                                    )}
                                                                    {isCompleted && (
                                                                        <button
                                                                            onClick={() => deletePipelineStep('text_recognition', n, true)}
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
                                                            {/* OCR Preview — Scrollable full text list */}
                                                            {showPreview && outputs?.ocr_texts && (
                                                                <div className="border-t border-slate-100 bg-slate-50 p-2">
                                                                    <div className="overflow-y-auto max-h-80 space-y-0.5">
                                                                        {outputs.ocr_texts.map((item: { filename: string, text: string }, idx: number) => {
                                                                            const lineImage = item.filename.replace(/\.txt$/i, '.png');
                                                                            return (
                                                                                <div key={idx} className="flex items-start gap-2 bg-white rounded border border-slate-100 px-2 py-1 hover:border-blue-200 transition-colors">
                                                                                    <span className="text-[9px] text-slate-400 w-6 text-right shrink-0 pt-0.5">{idx + 1}</span>
                                                                                    <img
                                                                                        src={`http://127.0.0.1:8000/media/${projectId}/nusha_${n}/lines/${lineImage}`}
                                                                                        alt={lineImage}
                                                                                        className="h-5 w-auto max-w-[120px] rounded border border-slate-200 shrink-0 cursor-pointer hover:border-blue-300 hover:shadow-sm transition-all mt-0.5"
                                                                                        loading="lazy"
                                                                                        onClick={() => setLightboxImage(`http://127.0.0.1:8000/media/${projectId}/nusha_${n}/lines/${lineImage}`)}
                                                                                    />
                                                                                    <p className="text-xs text-slate-700 flex-1 font-medium" dir="rtl" style={{ fontFamily: "'Amiri', 'Noto Naskh Arabic', serif", lineHeight: 1.6 }}>
                                                                                        {item.text || <span className="text-slate-300 italic">[boş]</span>}
                                                                                    </p>
                                                                                    <span className="text-[8px] text-slate-300 shrink-0 pt-0.5 max-w-[90px] truncate" title={lineImage}>{lineImage}</span>
                                                                                </div>
                                                                            );
                                                                        })}
                                                                    </div>
                                                                    <div className="text-[9px] text-slate-400 mt-1">{outputs.ocr_texts.length} satır metin (RTL) | Satır resmine tıklayarak büyütün</div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })()}

                                                {/* Step 4: Alignment */}
                                                {(() => {
                                                    const step = pipelineStatuses[n]?.steps?.alignment;
                                                    const isCompleted = step?.status === 'completed';
                                                    const isPending = step?.status === 'pending';
                                                    const isNotStarted = step?.status === 'not_started';
                                                    const requiresReference = step?.requires_reference;
                                                    const isRunning = processing === `alignment-${n}`;
                                                    const previewKey = `${n}-alignment`;
                                                    const showPreview = outputPreviews[previewKey] && isCompleted;
                                                    const outputs = pipelineOutputs[n];
                                                    const alignData = outputs?.alignment;

                                                    return (
                                                        <div className="bg-white border border-slate-200 rounded overflow-hidden">
                                                            <div className="p-2 flex items-center justify-between">
                                                                <div className="flex items-center gap-2">
                                                                    <span className="text-lg">🔗</span>
                                                                    <div>
                                                                        <div className="text-xs font-bold text-slate-700">Alignment (Eşleştirme)</div>
                                                                        {isCompleted && <div className="text-[10px] text-green-600">✅ Tamamlandı</div>}
                                                                        {isPending && !requiresReference && <div className="text-[10px] text-blue-500">⏸️ Bekliyor</div>}
                                                                        {requiresReference && <div className="text-[10px] text-orange-500">⚠️ Word dosyası gerekli</div>}
                                                                        {isNotStarted && !requiresReference && <div className="text-[10px] text-slate-400">⏸️ Önce OCR (Text Recognition) gerekli</div>}
                                                                        {isRunning && <div className="text-[10px] text-blue-600">⏳ İşleniyor...</div>}
                                                                    </div>
                                                                </div>
                                                                <div className="flex gap-1">
                                                                    {isCompleted && (
                                                                        <button
                                                                            onClick={() => togglePreview(n, 'alignment')}
                                                                            className={`px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 transition-colors ${showPreview ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 hover:bg-blue-50 text-slate-500 hover:text-blue-600'}`}
                                                                        >
                                                                            <Eye size={10} /> Debug
                                                                        </button>
                                                                    )}
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
                                                            {/* Alignment Debug Panel */}
                                                            {showPreview && alignData && !alignData.error && (
                                                                <div className="border-t border-slate-100 bg-slate-50 p-3 space-y-3">
                                                                    {/* Debug Summary */}
                                                                    <div className="bg-indigo-50 border border-indigo-100 rounded p-2">
                                                                        <div className="text-[10px] font-bold text-indigo-800 mb-1">📊 Alignment Özeti</div>
                                                                        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[10px]">
                                                                            <div className="text-slate-600">Algoritma: <span className="font-mono font-bold text-indigo-700">{alignData.debug?.algo_version}</span></div>
                                                                            <div className="text-slate-600">Word Kelime Sayısı: <span className="font-bold text-indigo-700">{alignData.debug?.tahkik_word_count}</span></div>
                                                                            <div className="text-slate-600">OCR Satır Sayısı: <span className="font-bold text-indigo-700">{alignData.debug?.lines_count}</span></div>
                                                                            <div className="text-slate-600">Spellcheck Hata: <span className="font-bold text-orange-600">{alignData.debug?.spellcheck_errors_count}</span></div>
                                                                        </div>
                                                                    </div>

                                                                    {/* Functions Executed — Expandable Panels */}
                                                                    <div className="bg-amber-50 border border-amber-100 rounded p-2">
                                                                        <div className="text-[10px] font-bold text-amber-800 mb-1">⚙️ Çalışan Fonksiyonlar ({alignData.functions_executed?.length || 0} adım)</div>
                                                                        <div className="space-y-1">
                                                                            {alignData.functions_executed?.map((fn: { name: string, description: string, output: string, data?: any }, idx: number) => {
                                                                                const fnKey = `${n}-fn-${idx}`;
                                                                                const isExpanded = expandedFunctions[fnKey];
                                                                                const hasData = fn.data && Object.keys(fn.data).length > 0;
                                                                                return (
                                                                                    <div key={idx} className={`rounded border transition-colors ${isExpanded ? 'border-amber-300 bg-white' : 'border-transparent'
                                                                                        }`}>
                                                                                        {/* Function header — clickable */}
                                                                                        <div
                                                                                            className={`flex items-start gap-2 text-[10px] p-1.5 rounded cursor-pointer hover:bg-amber-100/50 transition-colors`}
                                                                                            onClick={() => hasData && setExpandedFunctions(prev => ({ ...prev, [fnKey]: !prev[fnKey] }))}
                                                                                        >
                                                                                            {hasData ? (
                                                                                                isExpanded ? <ChevronDown size={12} className="text-amber-500 mt-0.5 shrink-0" /> : <ChevronRight size={12} className="text-amber-400 mt-0.5 shrink-0" />
                                                                                            ) : (
                                                                                                <span className="text-amber-400 mt-0.5 shrink-0 w-3 text-center">▸</span>
                                                                                            )}
                                                                                            <div className="flex-1 min-w-0">
                                                                                                <div className="flex items-center gap-1 flex-wrap">
                                                                                                    <span className="font-mono font-bold text-amber-900">{fn.name}</span>
                                                                                                    <span className="text-slate-400">—</span>
                                                                                                    <span className="text-slate-600">{fn.description}</span>
                                                                                                </div>
                                                                                                <div className="text-[9px] text-green-700 bg-green-50 rounded px-1.5 py-0.5 mt-0.5 inline-block">
                                                                                                    → {fn.output}
                                                                                                </div>
                                                                                            </div>
                                                                                        </div>
                                                                                        {/* Expanded data panel */}
                                                                                        {isExpanded && hasData && (
                                                                                            <div className="px-3 pb-2 pt-0">
                                                                                                <div className="bg-slate-50 border border-slate-200 rounded p-2 text-[9px] space-y-1.5 max-h-64 overflow-y-auto">
                                                                                                    {Object.entries(fn.data).map(([key, value]) => {
                                                                                                        // Render arrays as scrollable lists
                                                                                                        if (Array.isArray(value)) {
                                                                                                            return (
                                                                                                                <div key={key}>
                                                                                                                    <div className="font-bold text-slate-600 mb-0.5">{key} ({value.length}):</div>
                                                                                                                    <div className="bg-white rounded border border-slate-100 max-h-32 overflow-y-auto">
                                                                                                                        {value.map((item, i) => (
                                                                                                                            <div key={i} className="px-1.5 py-0.5 border-b border-slate-50 last:border-0 font-mono text-slate-700 hover:bg-blue-50" dir={typeof item === 'string' && /[\u0600-\u06FF]/.test(item) ? 'rtl' : 'ltr'}>
                                                                                                                                {typeof item === 'object' ? JSON.stringify(item) : String(item)}
                                                                                                                            </div>
                                                                                                                        ))}
                                                                                                                    </div>
                                                                                                                </div>
                                                                                                            );
                                                                                                        }
                                                                                                        // Render objects (like score_histogram, opcode_counts) as key-value grids
                                                                                                        if (typeof value === 'object' && value !== null) {
                                                                                                            return (
                                                                                                                <div key={key}>
                                                                                                                    <div className="font-bold text-slate-600 mb-0.5">{key}:</div>
                                                                                                                    <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 bg-white rounded border border-slate-100 p-1.5">
                                                                                                                        {Object.entries(value as Record<string, any>).map(([k, v]) => (
                                                                                                                            <div key={k} className="flex justify-between">
                                                                                                                                <span className="text-slate-500">{k}:</span>
                                                                                                                                <span className="font-mono font-bold text-indigo-700">{typeof v === 'number' ? v.toLocaleString() : String(v)}</span>
                                                                                                                            </div>
                                                                                                                        ))}
                                                                                                                    </div>
                                                                                                                </div>
                                                                                                            );
                                                                                                        }
                                                                                                        // Render simple values
                                                                                                        return (
                                                                                                            <div key={key} className="flex items-baseline gap-2">
                                                                                                                <span className="text-slate-500 shrink-0">{key}:</span>
                                                                                                                <span className="font-mono font-bold text-indigo-700" dir={typeof value === 'string' && /[\u0600-\u06FF]/.test(value) ? 'rtl' : 'ltr'}>
                                                                                                                    {typeof value === 'number' ? value.toLocaleString() : String(value)}
                                                                                                                </span>
                                                                                                            </div>
                                                                                                        );
                                                                                                    })}
                                                                                                </div>
                                                                                            </div>
                                                                                        )}
                                                                                    </div>
                                                                                );
                                                                            })}
                                                                        </div>
                                                                    </div>

                                                                    {/* Per-line Details — Scrollable table */}
                                                                    <div className="bg-white border border-slate-200 rounded">
                                                                        <div className="text-[10px] font-bold text-slate-700 p-2 border-b border-slate-100 flex items-center justify-between">
                                                                            <span>📋 Satır Detayları ({alignData.lines?.length} satır)</span>
                                                                            <span className="text-[9px] font-normal text-slate-400">Skor | Word Aralığı | OCR↔Ref Karşılaştırması</span>
                                                                        </div>
                                                                        <div className="overflow-y-auto max-h-96">
                                                                            <table className="w-full text-[10px]">
                                                                                <thead className="bg-slate-50 sticky top-0">
                                                                                    <tr>
                                                                                        <th className="px-2 py-1 text-left text-slate-500 font-medium w-8">#</th>
                                                                                        <th className="px-2 py-1 text-left text-slate-500 font-medium w-14">Skor</th>
                                                                                        <th className="px-2 py-1 text-left text-slate-500 font-medium w-20">Word Aralığı</th>
                                                                                        <th className="px-2 py-1 text-left text-slate-500 font-medium w-10">WC</th>
                                                                                        <th className="px-2 py-1 text-right text-slate-500 font-medium">OCR Metni</th>
                                                                                        <th className="px-2 py-1 text-right text-slate-500 font-medium">Referans Metin</th>
                                                                                    </tr>
                                                                                </thead>
                                                                                <tbody>
                                                                                    {alignData.lines?.map((line: any) => {
                                                                                        const scoreColor = line.score >= 0.8 ? 'text-green-700 bg-green-50' : line.score >= 0.5 ? 'text-yellow-700 bg-yellow-50' : 'text-red-700 bg-red-50';
                                                                                        return (
                                                                                            <tr key={line.line_no} className="border-t border-slate-50 hover:bg-blue-50/30">
                                                                                                <td className="px-2 py-1 text-slate-400">{line.line_no}</td>
                                                                                                <td className="px-2 py-1">
                                                                                                    <span className={`font-mono font-bold px-1 rounded ${scoreColor}`}>{line.score?.toFixed(3)}</span>
                                                                                                </td>
                                                                                                <td className="px-2 py-1 font-mono text-slate-500">{line.start_word}–{line.end_word}</td>
                                                                                                <td className="px-2 py-1 text-slate-400">{line.ocr_wc}/{line.seg_wc}</td>
                                                                                                <td className="px-2 py-1 text-right max-w-[200px] truncate" dir="rtl" style={{ fontFamily: "'Amiri', serif" }}>
                                                                                                    <span className={line.is_empty_ocr ? 'text-red-300 italic' : 'text-slate-700'}>
                                                                                                        {line.ocr_text || '[boş]'}
                                                                                                    </span>
                                                                                                </td>
                                                                                                <td className="px-2 py-1 text-right max-w-[200px] truncate" dir="rtl" style={{ fontFamily: "'Amiri', serif" }}>
                                                                                                    <span className="text-indigo-700">{line.ref_text || '[boş]'}</span>
                                                                                                </td>
                                                                                            </tr>
                                                                                        );
                                                                                    })}
                                                                                </tbody>
                                                                            </table>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })()}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Add New Nusha Button */}
                    <div className="mt-4 flex justify-center pb-10">
                        <label className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-bold shadow-sm transition-colors cursor-pointer ring-2 ring-purple-100 hover:ring-purple-300">
                            {uploading === 'new' ? <RefreshCw className="animate-spin" size={16} /> : <UploadCloud size={16} />}
                            Yeni Nüsha Ekle (PDF Yükle)
                            <input
                                type="file"
                                className="hidden"
                                accept=".pdf"
                                multiple
                                onChange={(e) => handleUpload(e.target.files, 'pdf', -1, 'new')}
                            />
                        </label>
                    </div>


                </div >
            </div >

            {/* Lightbox Modal */}
            {lightboxImage && (
                <div
                    className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 cursor-pointer"
                    onClick={() => setLightboxImage(null)}
                >
                    <button
                        className="absolute top-4 right-4 text-white/70 hover:text-white transition-colors z-10"
                        onClick={() => setLightboxImage(null)}
                    >
                        <XCircle size={32} />
                    </button>
                    <img
                        src={lightboxImage}
                        alt="Preview"
                        className="max-h-[90vh] max-w-[90vw] object-contain rounded-lg shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                    />
                </div>
            )}
        </>
    );
}
