"use client";

import React, { useEffect, useState } from "react";
import { X, RefreshCcw, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useMukabele } from "./MukabeleContext";

interface DeletedLine {
    line_no: number;
    ocr_text: string | null;
    ref_text: string | null;
    deleted_at: string;
}

export default function TrashBinDialog({
    isOpen,
    onClose
}: {
    isOpen: boolean;
    onClose: () => void;
}) {
    const params = useParams();
    const projectId = params.projectId as string;
    const { nushaIndex, refreshData } = useMukabele();

    const [deletedLines, setDeletedLines] = useState<DeletedLine[]>([]);
    const [loading, setLoading] = useState(false);
    const [restoring, setRestoring] = useState<number | null>(null);

    const fetchDeletedLines = async () => {
        setLoading(true);
        try {
            const res = await fetch(`http://localhost:8000/api/projects/${projectId}/lines/deleted?nusha_index=${nushaIndex}`);
            if (!res.ok) throw new Error("Failed to fetch deleted lines");
            const data = await res.json();
            setDeletedLines(data.lines || []);
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchDeletedLines();
        }
    }, [isOpen, projectId, nushaIndex]);

    const handleRestore = async (lineNo: number) => {
        setRestoring(lineNo);
        try {
            const res = await fetch(`http://localhost:8000/api/projects/${projectId}/lines/restore`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    line_no: lineNo,
                    nusha_index: nushaIndex
                })
            });

            if (!res.ok) throw new Error("Restore failed");

            // Remove from list
            setDeletedLines(prev => prev.filter(l => l.line_no !== lineNo));

            // Refresh main list
            await refreshData();

        } catch (error) {
            alert("Geri yükleme başarısız oldu.");
            console.error(error);
        } finally {
            setRestoring(null);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-white rounded-xl shadow-2xl w-[600px] max-h-[80vh] flex flex-col border border-slate-200">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                    <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                        <Trash2 size={20} className="text-slate-500" />
                        Silinen Satırlar
                    </h2>
                    <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-full text-slate-500 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-4 bg-slate-50 scrollbar-thin">
                    {loading ? (
                        <div className="text-center py-8 text-slate-400">Yükleniyor...</div>
                    ) : deletedLines.length === 0 ? (
                        <div className="text-center py-8 text-slate-400 flex flex-col items-center gap-2">
                            <Trash2 size={48} className="opacity-20" />
                            <p>Çöp kutusu boş.</p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {deletedLines.map(line => (
                                <div key={line.line_no} className="bg-white p-3 rounded-lg border border-slate-200 shadow-sm flex items-start justify-between gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-xs font-bold bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                                                Line {line.line_no}
                                            </span>
                                            <span className="text-[10px] text-slate-400">
                                                {line.deleted_at ? new Date(line.deleted_at).toLocaleString('tr-TR') : ""}
                                            </span>
                                        </div>
                                        <p className="text-sm text-slate-700 font-serif leading-relaxed line-clamp-2" dir="rtl">
                                            {line.ref_text || line.ocr_text || "(Boş Satır)"}
                                        </p>
                                    </div>

                                    <button
                                        onClick={() => handleRestore(line.line_no)}
                                        disabled={restoring === line.line_no}
                                        className="p-2 text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors disabled:opacity-50"
                                        title="Geri Yükle"
                                    >
                                        <RefreshCcw size={18} className={restoring === line.line_no ? "animate-spin" : ""} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-3 border-t border-slate-100 bg-white rounded-b-xl flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                    >
                        Kapat
                    </button>
                </div>
            </div>
        </div>
    );
}
