"use client";

import React, { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { MukabeleProvider, useMukabele } from "@/components/mukabele/MukabeleContext";
import { TTSProvider } from "@/components/mukabele/TTSContext";
import SplitPane from "@/components/mukabele/SplitPane";
import PageCanvas from "@/components/mukabele/PageCanvas";
import LineList from "@/components/mukabele/LineList";
import ImagePanelToolbar from "@/components/mukabele/ImagePanelToolbar";
import ImagePanelFooter from "@/components/mukabele/ImagePanelFooter";
import TextPanelToolbar from "@/components/mukabele/TextPanelToolbar";
import TextPanelFooter from "@/components/mukabele/TextPanelFooter";
import ErrorPopup from "@/components/mukabele/ErrorPopup";
import { ArrowLeft, BookOpen, Keyboard } from "lucide-react";

function MukabeleContent() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.id as string;
    const {
        data, setData,
        isLoading, setIsLoading,
        lines, pages,
        // nushaIndex, setNushaIndex, // Moved to ImagePanelToolbar
        // siglas,
    } = useMukabele();

    useEffect(() => {
        setIsLoading(true);
        fetch(`http://127.0.0.1:8000/api/projects/${projectId}/mukabele-data`)
            .then(res => res.json())
            .then(res => {
                setData(res);
                setIsLoading(false);
            })
            .catch(err => {
                console.error("Failed to load data", err);
                setIsLoading(false);
            });
    }, [projectId, setData, setIsLoading]);

    // Progress calculation
    const totalLines = lines.length;
    const errorLines = lines.filter(l => l.line_marks && l.line_marks.length > 0).length;
    const cleanLines = totalLines - errorLines;
    const progressPct = totalLines > 0 ? Math.round((cleanLines / totalLines) * 100) : 0;

    if (isLoading) {
        return (
            <div className="flex h-screen items-center justify-center text-slate-400 bg-slate-900">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500 mr-3"></div>
                <span className="text-sm">Mukabele verileri yükleniyor...</span>
            </div>
        );
    }

    if (!data || !pages.length) {
        return (
            <div className="flex h-screen flex-col items-center justify-center p-8 text-center bg-slate-900">
                <BookOpen size={48} className="text-slate-600 mb-4" />
                <h2 className="text-xl font-bold text-slate-300 mb-2">Veri Bulunamadı</h2>
                <p className="text-slate-500 mb-6">Bu proje için henüz hizalanmış veri yok.</p>
                <button
                    onClick={() => router.back()}
                    className="px-4 py-2 bg-slate-700 text-slate-200 rounded-lg hover:bg-slate-600 transition-colors"
                >
                    Geri Dön
                </button>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-screen overflow-hidden bg-slate-50">
            <ErrorPopup />

            {/* ── Slim Light Header ── */}
            <header className="flex items-center justify-between px-4 bg-white border-b border-slate-200 z-20 h-[42px] shrink-0 shadow-sm">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => router.back()}
                        className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                        title="Projeye Dön"
                    >
                        <ArrowLeft size={18} />
                    </button>
                    <div className="h-5 w-px bg-slate-200" />
                    <h1 className="font-semibold text-slate-700 flex items-center gap-2 text-sm">
                        <BookOpen size={16} className="text-amber-500" />
                        Mukabele
                    </h1>
                </div>

                {/* Center: Nüsha selector REMOVED (Moved to ImagePanelToolbar) */}

                {/* Right: Progress bar */}
                <div className="flex items-center gap-3">
                    {/* Progress */}
                    <div className="flex items-center gap-2">
                        <div className="w-24 h-1.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                            <div
                                className="h-full bg-gradient-to-r from-amber-500 to-emerald-500 rounded-full transition-all duration-500"
                                style={{ width: `${progressPct}%` }}
                            />
                        </div>
                        <span className="text-[10px] text-slate-500 font-mono tabular-nums w-8">
                            {progressPct}%
                        </span>
                    </div>
                </div>
            </header>

            {/* ── Main Content: Split Pane ── */}
            <div className="flex-1 overflow-hidden relative">
                <SplitPane
                    left={
                        <div className="flex flex-col h-full">
                            <ImagePanelToolbar />
                            <div className="flex-1 overflow-hidden">
                                <PageCanvas />
                            </div>
                            <ImagePanelFooter />
                        </div>
                    }
                    right={
                        <div className="flex flex-col h-full">
                            <TextPanelToolbar />
                            <div className="flex-1 overflow-hidden relative">
                                <LineList />
                            </div>
                            <TextPanelFooter />
                        </div>
                    }
                />
            </div>
        </div>
    );
}

export default function MukabelePage() {
    return (
        <MukabeleProvider>
            <TTSProvider>
                <MukabeleContent />
            </TTSProvider>
        </MukabeleProvider>
    );
}
