"use client";

import React, { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { MukabeleProvider, useMukabele } from "@/components/mukabele/MukabeleContext";
import SplitPane from "@/components/mukabele/SplitPane";
import ControlBar from "@/components/mukabele/ControlBar";
import PageCanvas from "@/components/mukabele/PageCanvas";
import LineList from "@/components/mukabele/LineList";
import { ArrowLeft, BookOpen } from "lucide-react";

import ErrorPopup from "@/components/mukabele/ErrorPopup";
import FloatingNav from "@/components/mukabele/FloatingNav";

function MukabeleContent() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.id as string;
    const {
        data, setData,
        isLoading, setIsLoading,
        pages
    } = useMukabele();

    useEffect(() => {
        setIsLoading(true);
        fetch(`http://localhost:8000/api/projects/${projectId}/mukabele-data`)
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

    if (isLoading) {
        return (
            <div className="flex h-screen items-center justify-center text-slate-500 bg-slate-50">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
                Mukabele verileri yükleniyor...
            </div>
        );
    }

    if (!data || !pages.length) {
        return (
            <div className="flex h-screen flex-col items-center justify-center p-8 text-center bg-slate-50">
                <h2 className="text-xl font-bold text-slate-800 mb-2">Veri Bulunamadı</h2>
                <p className="text-slate-500 mb-6">Bu proje için henüz hizalanmış veri yok.</p>
                <div className="flex gap-4">
                    <button
                        onClick={() => router.back()}
                        className="px-4 py-2 bg-slate-200 text-slate-700 rounded hover:bg-slate-300"
                    >
                        Geri Dön
                    </button>
                    {/* Could trigger analysis here if needed */}
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-screen overflow-hidden bg-slate-50">
            <ErrorPopup />
            <FloatingNav />

            {/* Header */}
            <header className="flex items-center justify-between px-4 py-2 bg-white border-b border-slate-200 shadow-sm z-20 h-[50px]">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => router.back()}
                        className="p-1 hovered:bg-slate-100 rounded text-slate-500 hover:text-slate-800 transition-colors"
                        title="Projeye Dön"
                    >
                        <ArrowLeft size={20} />
                    </button>
                    <h1 className="font-bold text-slate-800 flex items-center gap-2 text-sm md:text-base">
                        <BookOpen size={18} className="text-blue-600" />
                        Mukabele Ekranı
                    </h1>
                </div>
                {/* Extra header actions could go here */}
            </header>

            {/* Controls */}
            <ControlBar />

            {/* Main Content: Split Pane */}
            <div className="flex-1 overflow-hidden relative">
                <SplitPane
                    left={<PageCanvas />}
                    right={<LineList />}
                />
            </div>
        </div>
    );
}

export default function MukabelePage() {
    return (
        <MukabeleProvider>
            <MukabeleContent />
        </MukabeleProvider>
    );
}
