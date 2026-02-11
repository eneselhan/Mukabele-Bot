"use client";
import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
    BookOpen, X, Plus, Trash2, Monitor, PenTool, FolderOpen, ArrowLeft,
    Edit3, GripVertical, SortAsc, Clock, ChevronDown, ChevronRight,
    RotateCcw, Trash, FileText, Upload, File, UploadCloud, RefreshCw,
    Play, Check, Edit2, AlertCircle, CheckCircle
} from "lucide-react";

interface Project {
    id: string;
    name: string;
    authors?: string[];
    language?: string;
    subject?: string;
    description?: string;
    created_at?: string;
    has_alignment?: boolean;
    trashed?: boolean;
}

type SortMode = "manual" | "name-asc" | "name-desc" | "date-new" | "date-old";

const API = "http://localhost:8000";

export default function ProjectsPage() {
    const [projects, setProjects] = useState<Project[]>([]);
    const [trashedProjects, setTrashedProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingProject, setEditingProject] = useState<Project | null>(null);
    const [sortMode, setSortMode] = useState<SortMode>("manual");
    const [dragIdx, setDragIdx] = useState<number | null>(null);
    const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
    const [activeOpen, setActiveOpen] = useState(true);
    const [trashOpen, setTrashOpen] = useState(false);

    // Status & file data
    const [projectStatuses, setProjectStatuses] = useState<Record<string, any>>({});
    const [dpiSelections, setDpiSelections] = useState<Record<string, Record<number, number>>>({});
    const [selectedNushas, setSelectedNushas] = useState<Record<string, Set<number>>>({});
    const [processing, setProcessing] = useState<string | null>(null);
    const [uploading, setUploading] = useState<string | null>(null);

    // Modal state
    const [modalNushaNames, setModalNushaNames] = useState<Record<number, string>>({});
    const [modalNushaDrag, setModalNushaDrag] = useState<{ dragId: number } | null>(null);
    const [modalNushaOrder, setModalNushaOrder] = useState<number[]>([]);
    const [modalDpiSelections, setModalDpiSelections] = useState<Record<number, number>>({});

    const [formData, setFormData] = useState({
        name: "", authors: "", language: "Ottoman Turkish", subject: "Islamic Studies", description: ""
    });

    const router = useRouter();

    // ======== DATA FETCHING ========
    const fetchProjects = async () => {
        try {
            const [activeRes, trashRes] = await Promise.all([
                fetch(`${API}/api/projects`),
                fetch(`${API}/api/projects?trashed=true`)
            ]);
            const active = await activeRes.json();
            const trashed = await trashRes.json();
            setProjects(active);
            setTrashedProjects(trashed);
            // Fetch status for all active projects
            for (const p of active) {
                fetchProjectStatus(p.id);
            }
        } catch (err) { console.error("Proje listesi alınamadı:", err); }
        setLoading(false);
    };

    const fetchProjectStatus = useCallback(async (projectId: string) => {
        try {
            const res = await fetch(`${API}/api/projects/${projectId}/status`);
            if (res.ok) {
                const data = await res.json();
                setProjectStatuses(prev => ({ ...prev, [projectId]: data }));

                // Auto-select uploaded nushas that haven't been analyzed yet
                if (data.nushas) {
                    const nushas: any[] = Object.values(data.nushas);
                    setSelectedNushas(prev => {
                        const existing = prev[projectId] || new Set<number>();
                        const updated = new Set(existing);
                        for (const n of nushas) {
                            if (n.uploaded && n.progress?.status === 'completed') {
                                updated.delete(n.id); // Completed → uncheck
                            } else if (n.uploaded && n.progress?.status !== 'completed') {
                                updated.add(n.id); // Not analyzed → auto-select
                            }
                        }
                        return { ...prev, [projectId]: updated };
                    });
                }
            }
        } catch (err) { console.error("Status alınamadı:", err); }
    }, []);

    useEffect(() => { fetchProjects(); }, []);

    // Polling for processing projects
    useEffect(() => {
        if (!processing) return;
        const interval = setInterval(() => {
            projects.forEach(p => fetchProjectStatus(p.id));
        }, 3000);
        return () => clearInterval(interval);
    }, [processing, projects, fetchProjectStatus]);

    // ======== NUSHA SELECTION ========
    const toggleNushaSelection = (projectId: string, nushaId: number) => {
        setSelectedNushas(prev => {
            const set = new Set(prev[projectId] || []);
            if (set.has(nushaId)) set.delete(nushaId);
            else set.add(nushaId);
            return { ...prev, [projectId]: set };
        });
    };

    const getSelectedCount = (projectId: string): number => {
        return selectedNushas[projectId]?.size || 0;
    };

    // ======== ANALYSIS ========
    const runSelectedAnalysis = async (projectId: string) => {
        const selected = selectedNushas[projectId];
        if (!selected || selected.size === 0) return;
        const status = projectStatuses[projectId];
        if (!status?.has_tahkik) return;

        const ids = Array.from(selected);
        setProcessing(`${projectId}-batch`);

        for (const nushaId of ids) {
            try {
                const dpi = dpiSelections[projectId]?.[nushaId] || 300;
                setProcessing(`${projectId}-full-${nushaId}`);
                await fetch(`${API}/api/projects/${projectId}/nusha/${nushaId}/pipeline/full`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dpi })
                });
                // Poll until this nusha finishes
                let done = false;
                while (!done) {
                    await new Promise(r => setTimeout(r, 3000));
                    try {
                        const res = await fetch(`${API}/api/projects/${projectId}/status`);
                        if (res.ok) {
                            const d = await res.json();
                            setProjectStatuses(prev => ({ ...prev, [projectId]: d }));
                            const nusha = d.nushas ? Object.values(d.nushas).find((n: any) => n.id === nushaId) as any : null;
                            if (!nusha || nusha.progress?.status !== 'processing') done = true;
                        }
                    } catch { done = true; }
                }
                // Uncheck completed nusha
                setSelectedNushas(prev => {
                    const set = new Set(prev[projectId] || []);
                    set.delete(nushaId);
                    return { ...prev, [projectId]: set };
                });
            } catch (e) { console.error(`Nüsha ${nushaId} analiz hatası:`, e); }
        }
        setProcessing(null);
        await fetchProjectStatus(projectId);
    };

    // ======== FILE UPLOAD (from modal) ========
    const handleUpload = async (projectId: string, files: FileList | null, type: string, nushaIndex: number, loadingKey: string) => {
        if (!files || files.length === 0) return;
        setUploading(loadingKey);
        const fd = new FormData();
        Array.from(files).forEach(f => fd.append('files', f));
        fd.append('file_type', type);
        fd.append('nusha_index', nushaIndex.toString());
        try {
            const res = await fetch(`${API}/api/projects/${projectId}/upload`, { method: 'POST', body: fd });
            if (!res.ok) throw new Error('Upload failed');
            await fetchProjectStatus(projectId);
            // Auto-select new uploads
            if (type === 'pdf') {
                const statusRes = await fetch(`${API}/api/projects/${projectId}/status`);
                if (statusRes.ok) {
                    const data = await statusRes.json();
                    const nushas: any[] = data.nushas ? Object.values(data.nushas) : [];
                    setSelectedNushas(prev => {
                        const set = new Set(prev[projectId] || []);
                        for (const n of nushas) {
                            if (n.uploaded && n.progress?.status !== 'completed') set.add(n.id);
                        }
                        return { ...prev, [projectId]: set };
                    });
                }
            }
        } catch (e) { console.error(e); alert("Yükleme başarısız!"); }
        finally { setUploading(null); }
    };

    // ======== NUSHA ACTIONS (modal) ========
    const deleteNusha = async (projectId: string, nushaIndex: number) => {
        if (!confirm("Bu nüşayı silmek istediğinize emin misiniz?")) return;
        try {
            await fetch(`${API}/api/projects/${projectId}/files?file_type=pdf&nusha_index=${nushaIndex}`, { method: 'DELETE' });
            await fetchProjectStatus(projectId);
        } catch (e) { console.error(e); }
    };

    const saveNushaName = async (projectId: string, nushaIndex: number, name: string) => {
        try {
            await fetch(`${API}/api/projects/${projectId}/nusha/${nushaIndex}/name`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name })
            });
            fetchProjectStatus(projectId);
        } catch (e) { console.error(e); }
    };

    const saveNushaOrder = async (projectId: string, order: number[]) => {
        try {
            await fetch(`${API}/api/projects/${projectId}/order`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order })
            });
        } catch (e) { console.error("Order save failed", e); }
    };

    // ======== PROJECT CRUD ========
    const openCreateModal = () => {
        setEditingProject(null);
        setFormData({ name: "", authors: "", language: "Ottoman Turkish", subject: "Islamic Studies", description: "" });
        setModalNushaNames({});
        setModalNushaOrder([]);
        setModalDpiSelections({});
        setShowModal(true);
    };

    const openEditModal = (p: Project) => {
        setEditingProject(p);
        setFormData({
            name: p.name || "", authors: (p.authors || []).join(", "),
            language: p.language || "", subject: p.subject || "", description: p.description || ""
        });
        // Load nüsha data into modal
        const status = projectStatuses[p.id];
        if (status?.nushas) {
            const nushas: any[] = Object.values(status.nushas);
            const names: Record<number, string> = {};
            const dpis: Record<number, number> = {};
            nushas.forEach((n: any) => {
                names[n.id] = n.name || `Nüsha ${n.id}`;
                dpis[n.id] = dpiSelections[p.id]?.[n.id] || 300;
            });
            setModalNushaNames(names);
            setModalDpiSelections(dpis);
            const ids = nushas.map((n: any) => n.id).sort((a: number, b: number) => a - b);
            setModalNushaOrder(ids);
        } else {
            setModalNushaNames({});
            setModalNushaOrder([]);
            setModalDpiSelections({});
        }
        setShowModal(true);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formData.name) return;
        const payload = {
            name: formData.name,
            authors: formData.authors.split(",").map(s => s.trim()).filter(Boolean),
            language: formData.language, subject: formData.subject, description: formData.description
        };
        try {
            if (editingProject) {
                const res = await fetch(`${API}/api/projects/${editingProject.id}`, {
                    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
                });
                if (!res.ok) throw new Error("Güncelleme başarısız");
                // Save nusha names
                for (const [idStr, name] of Object.entries(modalNushaNames)) {
                    await saveNushaName(editingProject.id, parseInt(idStr), name);
                }
                // Save nusha order
                if (modalNushaOrder.length > 0) {
                    await saveNushaOrder(editingProject.id, modalNushaOrder);
                }
                // Save DPI selections
                setDpiSelections(prev => ({ ...prev, [editingProject.id]: { ...(prev[editingProject.id] || {}), ...modalDpiSelections } }));

                setProjects(prev => prev.map(p => p.id === editingProject.id ? { ...p, ...payload } : p));
                await fetchProjectStatus(editingProject.id);
                setShowModal(false);
            } else {
                const res = await fetch(`${API}/api/projects`, {
                    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
                });
                if (!res.ok) throw new Error("Proje oluşturulamadı");
                const newProject = await res.json();
                // Open edit modal for the new project to upload files
                setShowModal(false);
                await fetchProjects();
                setTimeout(() => {
                    const np: Project = { id: newProject.id, name: payload.name, authors: payload.authors, language: payload.language, subject: payload.subject, description: payload.description };
                    openEditModal(np);
                }, 500);
            }
        } catch (err) { alert("Hata: " + err); }
    };

    const handleTrashProject = async (id: string, e: React.MouseEvent) => {
        e.preventDefault(); e.stopPropagation();
        if (!confirm("Bu projeyi çöp kutusuna taşımak istediğinize emin misiniz?")) return;
        try {
            const res = await fetch(`${API}/api/projects/${id}/trash`, { method: "POST" });
            if (!res.ok) throw new Error("Çöp kutusuna taşınamadı");
            const project = projects.find(p => p.id === id);
            setProjects(prev => prev.filter(p => p.id !== id));
            if (project) setTrashedProjects(prev => [...prev, { ...project, trashed: true }]);
            if (!trashOpen) setTrashOpen(true);
        } catch (err) { alert("Hata: " + err); }
    };

    const handleRestoreProject = async (id: string) => {
        try {
            const res = await fetch(`${API}/api/projects/${id}/restore`, { method: "POST" });
            if (!res.ok) throw new Error("Geri yükleme başarısız");
            const project = trashedProjects.find(p => p.id === id);
            setTrashedProjects(prev => prev.filter(p => p.id !== id));
            if (project) setProjects(prev => [...prev, { ...project, trashed: false }]);
        } catch (err) { alert("Hata: " + err); }
    };

    const handlePermanentDelete = async (id: string) => {
        if (!confirm("Bu projeyi kalıcı olarak silmek istediğinize emin misiniz?")) return;
        try {
            const res = await fetch(`${API}/api/projects/${id}`, { method: "DELETE" });
            if (!res.ok) throw new Error("Kalıcı silme başarısız");
            setTrashedProjects(prev => prev.filter(p => p.id !== id));
        } catch (err) { alert("Hata: " + err); }
    };

    const handleDeleteAllTrashed = async () => {
        if (trashedProjects.length === 0) return;
        if (!confirm(`Çöp kutusundaki ${trashedProjects.length} projeyi kalıcı olarak silmek istediğinize emin misiniz? Bu işlem geri alınamaz!`)) return;
        try {
            const results = await Promise.allSettled(
                trashedProjects.map(p => fetch(`${API}/api/projects/${p.id}`, { method: "DELETE" }))
            );
            const failedCount = results.filter(r => r.status === 'rejected' || (r.status === 'fulfilled' && !r.value.ok)).length;
            setTrashedProjects([]);
            if (failedCount > 0) alert(`${failedCount} proje silinemedi.`);
        } catch (err) { alert("Hata: " + err); }
    };

    // ======== SORTING ========
    const sortedProjects = (() => {
        const arr = [...projects];
        switch (sortMode) {
            case "name-asc": return arr.sort((a, b) => (a.name || "").localeCompare(b.name || "", "tr"));
            case "name-desc": return arr.sort((a, b) => (b.name || "").localeCompare(a.name || "", "tr"));
            case "date-new": return arr.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
            case "date-old": return arr.sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
            default: return arr;
        }
    })();

    // Project drag and drop
    const handleDragStart = (idx: number) => { if (sortMode === "manual") setDragIdx(idx); };
    const handleDragOver = (e: React.DragEvent, idx: number) => { e.preventDefault(); if (sortMode === "manual") setDragOverIdx(idx); };
    const handleDrop = (idx: number) => {
        if (dragIdx === null || sortMode !== "manual") return;
        const reordered = [...projects]; const [moved] = reordered.splice(dragIdx, 1); reordered.splice(idx, 0, moved);
        setProjects(reordered); setDragIdx(null); setDragOverIdx(null);
    };
    const handleDragEnd = () => { setDragIdx(null); setDragOverIdx(null); };

    const sortOptions: { value: SortMode; label: string; icon: React.ReactNode }[] = [
        { value: "manual", label: "Manuel", icon: <GripVertical size={12} /> },
        { value: "name-asc", label: "A → Z", icon: <SortAsc size={12} /> },
        { value: "name-desc", label: "Z → A", icon: <SortAsc size={12} className="rotate-180" /> },
        { value: "date-new", label: "En Yeni", icon: <Clock size={12} /> },
        { value: "date-old", label: "En Eski", icon: <Clock size={12} /> },
    ];

    if (loading) return <div className="p-10 text-center text-gray-500">Yükleniyor...</div>;

    // ======== HELPERS ========
    const getNushas = (projectId: string): any[] => {
        const status = projectStatuses[projectId];
        if (!status?.nushas) return [];
        return Object.values(status.nushas);
    };

    const getNushaStatusBadge = (nusha: any) => {
        if (!nusha.uploaded) return <span className="text-[9px] bg-slate-100 text-slate-400 px-1.5 py-0.5 rounded font-bold">Dosya Yok</span>;
        if (nusha.progress?.status === 'processing') {
            return <span className="text-[9px] bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded font-bold animate-pulse">🔄 %{nusha.progress?.percent || 0}</span>;
        }
        if (nusha.progress?.status === 'completed') {
            return <span className="text-[9px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-bold flex items-center gap-0.5"><CheckCircle size={8} /> Hazır</span>;
        }
        if (nusha.progress?.status === 'failed') {
            return <span className="text-[9px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-bold">Hata</span>;
        }
        return <span className="text-[9px] bg-orange-100 text-orange-600 px-1.5 py-0.5 rounded font-bold">Bekleniyor</span>;
    };

    // ======== PROJECT ROW ========
    const renderProjectRow = (p: Project, idx: number, isTrashed: boolean, list: Project[]) => {
        const status = projectStatuses[p.id];
        const nushas = getNushas(p.id);
        const selectedCount = getSelectedCount(p.id);
        const isProjectProcessing = processing?.startsWith(`${p.id}-`);

        return (
            <div key={p.id}
                draggable={!isTrashed && sortMode === "manual"}
                onDragStart={() => !isTrashed && handleDragStart(idx)}
                onDragOver={(e) => !isTrashed && handleDragOver(e, idx)}
                onDrop={() => !isTrashed && handleDrop(idx)}
                onDragEnd={handleDragEnd}
                className={`px-4 py-3 group hover:bg-purple-50/40 transition-colors ${idx !== list.length - 1 ? 'border-b border-slate-100' : ''
                    } ${!isTrashed && dragIdx === idx ? 'opacity-40' : ''} ${!isTrashed && dragOverIdx === idx && dragIdx !== idx ? 'border-t-2 border-purple-400' : ''}`}
            >
                {/* Row 1: Project info + actions */}
                <div className="flex items-center gap-3">
                    {!isTrashed && (
                        <div className={`shrink-0 ${sortMode === 'manual' ? 'cursor-grab text-slate-300 hover:text-slate-500' : 'text-slate-100'}`}>
                            <GripVertical size={14} />
                        </div>
                    )}
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${isTrashed ? 'bg-slate-100 text-slate-400' : 'bg-purple-100 text-purple-600'}`}>
                        <BookOpen size={13} />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            <h2 className={`text-sm font-bold truncate ${isTrashed ? 'text-slate-500' : 'text-slate-800'}`}>{p.name}</h2>
                            {!isTrashed && status && (
                                status.has_tahkik
                                    ? <span className="text-[9px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-bold shrink-0">Word ✅</span>
                                    : <span className="text-[9px] bg-orange-100 text-orange-600 px-1.5 py-0.5 rounded font-bold shrink-0">Word ⚠️</span>
                            )}
                        </div>
                        {p.authors && p.authors.length > 0 && (
                            <p className="text-[10px] text-slate-400 truncate">{p.authors.join(", ")}</p>
                        )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0 flex-wrap justify-end">
                        {isTrashed ? (
                            <>
                                <button onClick={() => handleRestoreProject(p.id)} className="flex items-center gap-1 px-2.5 py-1.5 bg-green-50 hover:bg-green-100 text-green-700 border border-green-200 rounded-lg text-[10px] font-bold transition-colors"><RotateCcw size={11} /> Geri Al</button>
                                <button onClick={() => handlePermanentDelete(p.id)} className="flex items-center gap-1 px-2.5 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 rounded-lg text-[10px] font-bold transition-colors"><Trash2 size={11} /> Kalıcı Sil</button>
                            </>
                        ) : (
                            <>
                                <Link href={`/projects/${p.id}/editor`} className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-[10px] font-bold transition-colors"><PenTool size={11} /> Mukabele</Link>
                                <Link href={`/projects/${p.id}/process`} className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-100 hover:bg-blue-100 text-slate-600 hover:text-blue-700 rounded-lg text-[10px] font-bold transition-colors"><Monitor size={11} /> Detaylı Analiz</Link>
                                <button onClick={() => openEditModal(p)} className="flex items-center gap-1 px-2.5 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded-lg text-[10px] font-bold transition-colors"><Edit3 size={11} /> Düzenle</button>
                                <button onClick={(e) => handleTrashProject(p.id, e)} className="flex items-center gap-1 px-2.5 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 rounded-lg text-[10px] font-bold transition-colors"><Trash size={11} /> Sil</button>
                            </>
                        )}
                    </div>
                </div>

                {/* Row 2: Nüsha cards — only for active projects */}
                {!isTrashed && nushas.length > 0 && (
                    <div className="mt-2.5 ml-10 mr-2">
                        <div className="bg-slate-50/80 rounded-lg border border-slate-100 p-2 space-y-1.5">
                            {nushas.sort((a: any, b: any) => (a.name || `Nüsha ${a.id}`).localeCompare(b.name || `Nüsha ${b.id}`, 'tr')).map((nusha: any) => {
                                const isSelected = selectedNushas[p.id]?.has(nusha.id) || false;
                                const isThisProcessing = processing === `${p.id}-full-${nusha.id}`;
                                const currentDpi = dpiSelections[p.id]?.[nusha.id] || 300;

                                return (
                                    <div key={nusha.id} className={`flex items-center gap-2.5 bg-white rounded-md border px-3 py-1.5 transition-all ${isThisProcessing ? 'border-blue-300 bg-blue-50/50 shadow-sm'
                                        : isSelected ? 'border-green-300 bg-green-50/30'
                                            : 'border-slate-200 hover:border-slate-300'}`}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={() => toggleNushaSelection(p.id, nusha.id)}
                                            disabled={isThisProcessing}
                                            className="w-3.5 h-3.5 rounded border-slate-300 text-green-600 focus:ring-green-500 cursor-pointer accent-green-600 shrink-0"
                                        />
                                        <div className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold shrink-0 ${nusha.uploaded ? 'bg-purple-100 text-purple-700' : 'bg-slate-200 text-slate-400'}`}>{nusha.id}</div>
                                        <span className={`text-[11px] font-semibold flex-1 min-w-0 truncate ${isThisProcessing ? 'text-blue-600' : 'text-slate-700'}`}>
                                            {nusha.name || `Nüsha ${nusha.id}`}
                                        </span>
                                        <select
                                            className="bg-slate-50 border border-slate-200 text-[9px] text-slate-500 rounded px-1.5 py-0.5 outline-none cursor-pointer hover:border-blue-300 font-medium w-[52px] shrink-0"
                                            value={currentDpi}
                                            onChange={(e) => setDpiSelections(prev => ({
                                                ...prev, [p.id]: { ...(prev[p.id] || {}), [nusha.id]: Number(e.target.value) }
                                            }))}
                                        >
                                            <option value={200}>200</option>
                                            <option value={300}>300</option>
                                            <option value={400}>400</option>
                                        </select>
                                        {getNushaStatusBadge(nusha)}
                                        {isThisProcessing && <RefreshCw className="animate-spin text-blue-500 shrink-0" size={10} />}
                                    </div>
                                );
                            })}

                            {/* Analyze button at the bottom of nüsha list */}
                            <button
                                onClick={() => runSelectedAnalysis(p.id)}
                                disabled={!status?.has_tahkik || selectedCount === 0 || !!isProjectProcessing}
                                className={`w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[11px] font-bold transition-all mt-1 ${isProjectProcessing
                                    ? 'bg-green-100 text-green-700 border border-green-300 cursor-wait'
                                    : !status?.has_tahkik || selectedCount === 0
                                        ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                                        : 'bg-green-600 hover:bg-green-700 text-white shadow-sm'
                                    }`}
                                title={!status?.has_tahkik ? 'Önce Word yükleyin' : selectedCount === 0 ? 'Analiz edilecek nüsha seçin' : `${selectedCount} nüshayı sırayla analiz et`}
                            >
                                {isProjectProcessing ? <RefreshCw className="animate-spin" size={12} /> : <Play size={12} fill="currentColor" />}
                                {isProjectProcessing ? 'Analiz Devam Ediyor...' : selectedCount > 0 ? `Seçilileri Analiz Et (${selectedCount})` : 'Analiz için nüsha seçin'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    // ======== MODAL: NÜSHA DRAG ========
    const handleModalNushaDragOver = (e: React.DragEvent, targetId: number) => {
        e.preventDefault();
        if (!modalNushaDrag || modalNushaDrag.dragId === targetId) return;
        const order = [...modalNushaOrder];
        const fromIdx = order.indexOf(modalNushaDrag.dragId);
        const toIdx = order.indexOf(targetId);
        if (fromIdx === -1 || toIdx === -1) return;
        order.splice(fromIdx, 1);
        order.splice(toIdx, 0, modalNushaDrag.dragId);
        setModalNushaOrder(order);
    };

    // ======== RENDER ========
    return (
        <main className="min-h-screen bg-slate-50">
            {/* Header */}
            <div className="bg-white border-b border-slate-200 shadow-sm">
                <div className="max-w-6xl mx-auto px-4 py-3 flex justify-between items-center">
                    <div className="flex items-center gap-3">
                        <Link href="/" className="text-slate-400 hover:text-slate-600 transition-colors"><ArrowLeft size={18} /></Link>
                        <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-lg bg-purple-600 flex items-center justify-center text-white"><BookOpen size={16} /></div>
                            <div>
                                <h1 className="text-base font-bold text-slate-800 leading-tight">Projelerim</h1>
                                <p className="text-[11px] text-slate-400">Tahkik projelerinizi yönetin</p>
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="flex items-center bg-slate-100 rounded-lg p-0.5 gap-0.5">
                            {sortOptions.map(opt => (
                                <button key={opt.value} onClick={() => setSortMode(opt.value)}
                                    className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-bold transition-all ${sortMode === opt.value ? 'bg-white text-purple-700 shadow-sm' : 'text-slate-400 hover:text-slate-600'}`} title={opt.label}>
                                    {opt.icon}<span className="hidden sm:inline">{opt.label}</span>
                                </button>
                            ))}
                        </div>
                        <button onClick={openCreateModal} className="bg-purple-600 text-white px-3.5 py-1.5 rounded-lg hover:bg-purple-700 transition shadow-sm flex items-center gap-1.5 text-xs font-bold">
                            <Plus size={14} /> Yeni Proje
                        </button>
                    </div>
                </div>
            </div>

            <div className="max-w-6xl mx-auto px-4 py-4 space-y-4">
                {/* Active Projects */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                    <button onClick={() => setActiveOpen(!activeOpen)} className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-200 hover:bg-slate-100 transition-colors">
                        <div className="flex items-center gap-2">
                            {activeOpen ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
                            <span className="text-xs font-bold text-slate-600">Aktif Projeler</span>
                            <span className="text-[10px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full font-bold">{projects.length}</span>
                        </div>
                    </button>
                    {activeOpen && (
                        <>
                            {projects.length === 0 ? (
                                <div className="text-center py-12 text-slate-500">
                                    <FolderOpen size={36} className="mx-auto text-slate-300 mb-3" />
                                    <h3 className="text-sm font-bold text-slate-600">Henüz hiç proje yok</h3>
                                    <p className="text-xs text-slate-400 mt-1">Yeni bir tane oluşturarak başlayın!</p>
                                    <button onClick={openCreateModal} className="mt-4 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition text-sm font-bold inline-flex items-center gap-1.5"><Plus size={14} /> İlk Projenizi Oluşturun</button>
                                </div>
                            ) : (
                                <>
                                    {sortedProjects.map((p, idx) => renderProjectRow(p, idx, false, sortedProjects))}
                                    <div className="px-4 py-2 bg-slate-50 border-t border-slate-100 text-[11px] text-slate-400">Toplam {projects.length} proje</div>
                                </>
                            )}
                        </>
                    )}
                </div>

                {/* Trash */}
                {(trashedProjects.length > 0 || trashOpen) && (
                    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                        <button onClick={() => setTrashOpen(!trashOpen)} className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-200 hover:bg-slate-100 transition-colors">
                            <div className="flex items-center gap-2">
                                {trashOpen ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
                                <Trash2 size={13} className="text-slate-400" />
                                <span className="text-xs font-bold text-slate-500">Çöp Kutusu</span>
                                {trashedProjects.length > 0 && <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full font-bold">{trashedProjects.length}</span>}
                            </div>
                        </button>
                        {trashOpen && (
                            <>
                                {trashedProjects.length === 0 ? (
                                    <div className="text-center py-8 text-slate-400"><Trash2 size={28} className="mx-auto text-slate-200 mb-2" /><p className="text-xs">Çöp kutusu boş</p></div>
                                ) : (
                                    <>
                                        {trashedProjects.map((p, idx) => renderProjectRow(p, idx, true, trashedProjects))}
                                        <div className="px-4 py-2 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
                                            <span className="text-[11px] text-slate-400">{trashedProjects.length} proje çöp kutusunda</span>
                                            <button
                                                onClick={handleDeleteAllTrashed}
                                                className="flex items-center gap-1 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white rounded-lg text-[10px] font-bold transition-colors shadow-sm"
                                            >
                                                <Trash2 size={11} />
                                                Tümünü Kalıcı Sil
                                            </button>
                                        </div>
                                    </>
                                )}
                            </>
                        )}
                    </div>
                )}
            </div>

            {/* ======== EDIT / CREATE MODAL ======== */}
            {showModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm p-4">
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto relative animate-in fade-in zoom-in duration-200">
                        <button onClick={() => setShowModal(false)} className="absolute top-3 right-3 text-slate-400 hover:text-slate-600 z-10"><X size={18} /></button>

                        <div className="p-6 space-y-5">
                            <div>
                                <h2 className="text-lg font-bold text-slate-800">{editingProject ? "Proje Yönetimi" : "Yeni Proje Oluştur"}</h2>
                                <p className="text-xs text-slate-400 mt-0.5">{editingProject ? "Proje bilgilerini, referans metin ve nüshaları yönetin." : "Proje bilgilerini girin, ardından dosyalarınızı yükleyin."}</p>
                            </div>

                            {/* Section 1: Project Info */}
                            <form onSubmit={handleSubmit} className="space-y-4">
                                <div className="bg-slate-50 rounded-lg p-4 space-y-3">
                                    <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide">Proje Bilgileri</h3>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-600 mb-1">Proje/Eser Adı</label>
                                        <input required className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all" placeholder="Örn: Fütüvvetname" value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-600 mb-1">Yazar(lar)</label>
                                        <input className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all" placeholder="Virgülle ayırın" value={formData.authors} onChange={e => setFormData({ ...formData, authors: e.target.value })} />
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div><label className="block text-xs font-bold text-slate-600 mb-1">Dil</label><input className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all" value={formData.language} onChange={e => setFormData({ ...formData, language: e.target.value })} /></div>
                                        <div><label className="block text-xs font-bold text-slate-600 mb-1">Konu</label><input className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all" value={formData.subject} onChange={e => setFormData({ ...formData, subject: e.target.value })} /></div>
                                    </div>
                                    <div><label className="block text-xs font-bold text-slate-600 mb-1">Açıklama</label><textarea className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all h-16 resize-none" placeholder="Kısa bilgi..." value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })} /></div>
                                </div>

                                {/* Section 2: Word File (only in edit mode) */}
                                {editingProject && (
                                    <div className="bg-indigo-50/50 rounded-lg p-4 space-y-2">
                                        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                                            <BookOpen size={12} className="text-indigo-500" /> Referans Metin (Word)
                                        </h3>
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                {projectStatuses[editingProject.id]?.has_tahkik
                                                    ? <span className="text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-lg font-bold flex items-center gap-0.5"><CheckCircle size={10} /> Yüklendi</span>
                                                    : <span className="text-[10px] bg-orange-100 text-orange-700 px-2 py-0.5 rounded-lg font-bold flex items-center gap-0.5"><AlertCircle size={10} /> Bekleniyor</span>
                                                }
                                            </div>
                                            <label className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-all ${projectStatuses[editingProject.id]?.has_tahkik
                                                ? 'bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-600'
                                                : 'bg-indigo-600 text-white hover:bg-indigo-700'
                                                }`}>
                                                {uploading === `modal-docx` ? <RefreshCw className="animate-spin" size={12} /> : <UploadCloud size={12} />}
                                                {projectStatuses[editingProject.id]?.has_tahkik ? "Güncelle" : "Word Yükle"}
                                                <input type="file" className="hidden" accept=".docx" onChange={(e) => handleUpload(editingProject.id, e.target.files, 'docx', 1, 'modal-docx')} />
                                            </label>
                                        </div>
                                    </div>
                                )}

                                {/* Section 3: Nüshalar (only in edit mode) */}
                                {editingProject && (
                                    <div className="bg-purple-50/50 rounded-lg p-4 space-y-3">
                                        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                                            <FileText size={12} className="text-purple-500" /> Nüshalar
                                        </h3>

                                        {(() => {
                                            const nushas = getNushas(editingProject.id);
                                            const order = modalNushaOrder.length > 0 ? modalNushaOrder : nushas.map((n: any) => n.id).sort((a: number, b: number) => a - b);

                                            return (
                                                <>
                                                    {nushas.length === 0 ? (
                                                        <p className="text-xs text-slate-400 italic">Henüz nüsha yüklenmedi.</p>
                                                    ) : (
                                                        <div className="space-y-1.5">
                                                            {order.map((nushaId: number) => {
                                                                const nusha = nushas.find((n: any) => n.id === nushaId);
                                                                if (!nusha) return null;

                                                                return (
                                                                    <div
                                                                        key={nusha.id}
                                                                        draggable
                                                                        onDragStart={() => setModalNushaDrag({ dragId: nusha.id })}
                                                                        onDragOver={(e) => handleModalNushaDragOver(e, nusha.id)}
                                                                        onDragEnd={() => setModalNushaDrag(null)}
                                                                        className={`bg-white border border-slate-200 rounded-lg p-2.5 flex items-center gap-3 ${modalNushaDrag?.dragId === nusha.id ? 'opacity-50 ring-2 ring-purple-300' : ''}`}
                                                                    >
                                                                        <div className="text-slate-300 cursor-grab active:cursor-grabbing hover:text-slate-500 shrink-0"><GripVertical size={14} /></div>
                                                                        <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${nusha.uploaded ? 'bg-purple-100 text-purple-700' : 'bg-slate-200 text-slate-400'}`}>{nusha.id}</div>
                                                                        <input
                                                                            className="flex-1 text-xs border border-slate-200 rounded px-2 py-1 focus:ring-1 focus:ring-purple-400 focus:border-purple-400 outline-none min-w-0"
                                                                            value={modalNushaNames[nusha.id] || nusha.name || `Nüsha ${nusha.id}`}
                                                                            onChange={(e) => setModalNushaNames(prev => ({ ...prev, [nusha.id]: e.target.value }))}
                                                                            placeholder="Nüsha adı..."
                                                                        />
                                                                        <select
                                                                            className="bg-slate-50 border border-slate-200 text-[10px] text-slate-600 rounded px-1.5 py-1 outline-none cursor-pointer hover:border-blue-300 font-medium w-16 shrink-0"
                                                                            value={modalDpiSelections[nusha.id] || 300}
                                                                            onChange={(e) => setModalDpiSelections(prev => ({ ...prev, [nusha.id]: Number(e.target.value) }))}
                                                                        >
                                                                            <option value={200}>200 DPI</option>
                                                                            <option value={300}>300 DPI</option>
                                                                            <option value={400}>400 DPI</option>
                                                                        </select>
                                                                        {nusha.uploaded && (
                                                                            <label className="text-[10px] text-blue-500 hover:text-blue-700 cursor-pointer shrink-0 flex items-center gap-0.5">
                                                                                <RefreshCw size={9} /> Değiştir
                                                                                <input type="file" className="hidden" accept=".pdf" onChange={(e) => handleUpload(editingProject.id, e.target.files, 'pdf', nusha.id, `modal-n${nusha.id}`)} />
                                                                            </label>
                                                                        )}
                                                                        {nusha.filename && <span className="text-[9px] text-slate-400 truncate max-w-[80px] shrink-0" title={nusha.filename}>{nusha.filename}</span>}
                                                                        {getNushaStatusBadge(nusha)}
                                                                        <button onClick={() => deleteNusha(editingProject.id, nusha.id)} className="text-slate-300 hover:text-red-500 shrink-0 transition-colors" title="Sil"><Trash2 size={13} /></button>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    )}

                                                    <label className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-[10px] font-bold cursor-pointer transition-colors shadow-sm">
                                                        {uploading === `modal-new` ? <RefreshCw className="animate-spin" size={12} /> : <UploadCloud size={12} />}
                                                        Yeni Nüsha Ekle (PDF)
                                                        <input type="file" className="hidden" accept=".pdf" multiple onChange={(e) => {
                                                            handleUpload(editingProject.id, e.target.files, 'pdf', -1, 'modal-new');
                                                        }} />
                                                    </label>
                                                </>
                                            );
                                        })()}
                                    </div>
                                )}

                                {/* Submit */}
                                <div className="flex gap-2 pt-1">
                                    <button type="button" onClick={() => setShowModal(false)} className="flex-1 bg-slate-100 text-slate-600 py-2 rounded-lg hover:bg-slate-200 text-sm font-bold transition-colors">İptal</button>
                                    <button type="submit" className="flex-1 bg-purple-600 text-white py-2 rounded-lg hover:bg-purple-700 text-sm font-bold transition-colors shadow-sm">{editingProject ? "Kaydet" : "Oluştur"}</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}
