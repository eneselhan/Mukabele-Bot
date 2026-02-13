"use client";

import React, { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useMukabele } from "./MukabeleContext";
import {
    Search, X, ChevronUp, ChevronDown,
    Type, AlertTriangle, ChevronRight,
    List, FileText, Download, Trash2
} from "lucide-react";
import TrashBinDialog from "./TrashBinDialog";

export default function TextPanelToolbar() {
    const params = useParams();
    const {
        fontSize, setFontSize,
        searchQuery, setSearchQuery,
        searchMatches, currentSearchIndex,
        nextSearch, prevSearch,
        lines, setActiveLine,
        viewMode, setViewMode,
        // nushaIndex etc removed as used in ImagePanel
    } = useMukabele();

    const [showSearch, setShowSearch] = useState(false);
    const [showErrors, setShowErrors] = useState(false);
    const [showTrash, setShowTrash] = useState(false);

    const [navState, setNavState] = useState<{ [key: string]: number }>({});

    // Error groups (from FloatingNav logic)
    const errorGroups = useMemo(() => {
        const groups: { [key: string]: number[] } = {
            gemini: [], openai: [], claude: [],
            gptgem: [], gptclaude: [], all3: []
        };
        lines.forEach(line => {
            const marks = line.line_marks || [];
            if (!marks.length) return;
            const sources = new Set<string>();
            marks.forEach((m: any) => {
                (m.sources || []).forEach((s: string) => sources.add(s));
            });
            if (sources.has("gemini")) groups.gemini.push(line.line_no);
            if (sources.has("openai")) groups.openai.push(line.line_no);
            if (sources.has("claude")) groups.claude.push(line.line_no);
            if (sources.has("gemini") && sources.has("openai")) groups.gptgem.push(line.line_no);
            if (sources.has("openai") && sources.has("claude")) groups.gptclaude.push(line.line_no);
            if (sources.has("gemini") && sources.has("openai") && sources.has("claude")) groups.all3.push(line.line_no);
        });
        return groups;
    }, [lines]);

    const totalErrors = errorGroups.gemini.length + errorGroups.openai.length + errorGroups.claude.length;

    const jumpTo = (key: string) => {
        const list = errorGroups[key];
        if (!list.length) return;
        let idx = navState[key] ?? -1;
        idx = (idx + 1) % list.length;
        setNavState(prev => ({ ...prev, [key]: idx }));
        setActiveLine(list[idx]);
    };

    return (
        <div className="bg-white border-b border-slate-200 shrink-0">
            {/* Trash Bin Dialog */}
            <TrashBinDialog isOpen={showTrash} onClose={() => setShowTrash(false)} />

            {/* Main toolbar row */}
            <div className="flex items-center justify-between px-3 py-1.5 text-xs">

                {/* LEFT: Search & Trash */}
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowSearch(!showSearch)}
                        className={`p-1.5 rounded transition-colors ${showSearch ? "text-amber-600 bg-amber-50 ring-1 ring-amber-200" : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"}`}
                        title="Ara (Ctrl+F)"
                    >
                        <Search size={14} />
                    </button>

                    <div className="h-4 w-px bg-slate-200 mx-1" />

                    <button
                        onClick={() => setShowTrash(true)}
                        className={`p-1.5 rounded transition-colors text-slate-500 hover:text-red-600 hover:bg-red-50`}
                        title="Çöp Kutusu"
                    >
                        <Trash2 size={14} />
                    </button>
                </div>

                {/* CENTER: View Mode & Font Size */}
                <div className="flex items-center gap-4">
                    {/* View Mode */}
                    <div className="flex bg-slate-100 rounded-lg p-0.5 border border-slate-200/50">
                        <button
                            onClick={() => setViewMode('list')}
                            className={`px-2 py-0.5 rounded-md flex items-center gap-1.5 transition-all ${viewMode === 'list' ? 'bg-white text-slate-700 shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}
                            title="Liste Görünümü"
                        >
                            <List size={13} />
                            <span className="font-medium">Liste</span>
                        </button>
                        <button
                            onClick={() => setViewMode('paper')}
                            className={`px-2 py-0.5 rounded-md flex items-center gap-1.5 transition-all ${viewMode === 'paper' ? 'bg-white text-slate-700 shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}
                            title="Kağıt Görünümü"
                        >
                            <FileText size={13} />
                            <span className="font-medium">Kağıt</span>
                        </button>
                    </div>

                    {/* Font Size */}
                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => setFontSize(Math.max(10, fontSize - 1))}
                            className="w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
                        >
                            <Type size={10} />
                        </button>
                        <span className="text-slate-600 font-mono w-4 text-center tabular-nums text-[10px]">{fontSize}</span>
                        <button
                            onClick={() => setFontSize(Math.min(40, fontSize + 1))}
                            className="w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
                        >
                            <Type size={14} />
                        </button>
                    </div>
                </div>

                {/* RIGHT: Errors & Download */}
                <div className="flex items-center gap-3">
                    {/* Error nav dropdown toggle */}
                    <div className="relative">
                        <button
                            onClick={() => setShowErrors(!showErrors)}
                            className={`flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${showErrors
                                ? "text-amber-600 bg-amber-50"
                                : totalErrors > 0
                                    ? "text-amber-500/90 hover:text-amber-600 hover:bg-amber-50"
                                    : "text-slate-300 hover:text-slate-500"
                                }`}
                            title={totalErrors > 0 ? `${totalErrors} Hata Bulundu` : "Hata Yok"}
                        >
                            <AlertTriangle size={14} />
                            {totalErrors > 0 && (
                                <span className="bg-amber-100 text-amber-700 px-1.5 rounded-full text-[10px] font-bold tabular-nums">
                                    {totalErrors}
                                </span>
                            )}
                        </button>

                        {/* Error dropdown panel */}
                        {showErrors && (
                            <div className="absolute right-0 top-full mt-2 w-56 bg-white border border-slate-200 rounded-lg shadow-xl z-50 p-2 space-y-1">
                                <ErrorNavBtn label="Gemini" count={errorGroups.gemini.length} onClick={() => jumpTo("gemini")} color="text-blue-500" />
                                <ErrorNavBtn label="GPT" count={errorGroups.openai.length} onClick={() => jumpTo("openai")} color="text-green-500" />
                                <ErrorNavBtn label="Claude" count={errorGroups.claude.length} onClick={() => jumpTo("claude")} color="text-orange-500" />
                                <div className="h-px bg-slate-100 my-1" />
                                <ErrorNavBtn label="GPT + Gemini" count={errorGroups.gptgem.length} onClick={() => jumpTo("gptgem")} color="text-teal-500" />
                                <ErrorNavBtn label="GPT + Claude" count={errorGroups.gptclaude.length} onClick={() => jumpTo("gptclaude")} color="text-yellow-500" />
                                <ErrorNavBtn label="3'ü Ortak" count={errorGroups.all3.length} onClick={() => jumpTo("all3")} color="text-red-500" />
                            </div>
                        )}
                    </div>

                    <div className="h-4 w-px bg-slate-200" />

                    <button
                        onClick={async () => {
                            if (!window.confirm("Word dosyası indirilsin mi?")) return;
                            try {
                                const response = await fetch(`http://127.0.0.1:8000/api/projects/${params.id}/export/docx`, {
                                    method: 'POST',
                                });
                                if (!response.ok) {
                                    const errorData = await response.json().catch(() => ({}));
                                    throw new Error(errorData.detail || 'Dosya oluşturulamadı.');
                                }
                                const blob = await response.blob();
                                const url = window.URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = url;
                                a.download = `project-${params.id}.docx`;
                                document.body.appendChild(a);
                                a.click();
                                window.URL.revokeObjectURL(url);
                                a.remove();
                            } catch (e: any) {
                                console.error('Export error:', e);
                                alert(`Word dosyası indirilemedi: ${e.message}`);
                            }
                        }}
                        className="flex items-center gap-1.5 px-2 py-1 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        title="Word Olarak İndir"
                    >
                        <Download size={14} />
                        <span className="font-medium hidden lg:inline">İndir</span>
                    </button>
                </div>
            </div>

            {/* Search Bar Row (Conditional) */}
            {showSearch && (
                <div className="bg-slate-50 border-t border-slate-200 px-3 py-2 flex items-center gap-2 animate-in slide-in-from-top-2 duration-200">
                    <div className="relative flex-1">
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Metin içinde ara..."
                            className="w-full pl-8 pr-4 py-1.5 bg-white border border-slate-300 rounded-md text-slate-700 text-xs focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none"
                            autoFocus
                        />
                        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                    </div>
                    <div className="flex items-center gap-1 text-slate-500 text-[10px] font-mono whitespace-nowrap">
                        {searchMatches.length > 0 ? (
                            <>
                                <span>{currentSearchIndex + 1} / {searchMatches.length}</span>
                                <div className="flex gap-0.5">
                                    <button onClick={prevSearch} className="p-1 hover:bg-slate-200 rounded"><ChevronUp size={14} /></button>
                                    <button onClick={nextSearch} className="p-1 hover:bg-slate-200 rounded"><ChevronDown size={14} /></button>
                                </div>
                            </>
                        ) : searchQuery ? (
                            <span className="text-slate-400 italic">Sonuç yok</span>
                        ) : null}
                    </div>
                    <button onClick={() => setShowSearch(false)} className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded">
                        <X size={14} />
                    </button>
                </div>
            )}
        </div>
    );
}

// Helper for Error Nav logic
function ErrorNavBtn({ label, count, onClick, color }: { label: string, count: number, onClick: () => void, color: string }) {
    if (count === 0) return null;
    return (
        <button
            onClick={onClick}
            className="w-full flex items-center justify-between px-2 py-1.5 hover:bg-slate-50 rounded text-left text-xs transition-colors"
        >
            <span className="text-slate-600 font-medium">{label}</span>
            <span className={`font-bold ${color}`}>{count}</span>
        </button>
    );
}
