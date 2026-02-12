"use client";

import React, { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useMukabele } from "./MukabeleContext";
import {
    Search, X, ChevronUp, ChevronDown,
    Type, AlertTriangle, ChevronRight,
    List, FileText, Download, Settings
} from "lucide-react";

export default function TextPanelToolbar() {
    const params = useParams();
    const {
        fontSize, setFontSize,
        searchQuery, setSearchQuery,
        searchMatches, currentSearchIndex,
        nextSearch, prevSearch,
        lines, setActiveLine,
        viewMode, setViewMode,
        siglas, updateSigla, nushaIndex,
        baseNushaIndex, updateBaseNusha
    } = useMukabele();

    const [showSearch, setShowSearch] = useState(false);
    const [showErrors, setShowErrors] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [editingSigla, setEditingSigla] = useState(false);
    const [tempSigla, setTempSigla] = useState("");
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
        <div className="bg-slate-800 border-b border-slate-700 shrink-0">
            {/* Main toolbar row */}
            <div className="flex items-center justify-between px-3 py-1.5 text-xs">
                {/* Search toggle + Font controls */}
                <div className="flex items-center gap-3">
                    {/* Search toggle */}
                    <button
                        onClick={() => setShowSearch(!showSearch)}
                        className={`p-1 rounded transition-colors ${showSearch ? "text-amber-400 bg-slate-700" : "text-slate-400 hover:text-white hover:bg-slate-700"}`}
                        title="Ara (Ctrl+F)"
                    >
                        <Search size={14} />
                    </button>

                    {/* View Mode Toggle */}
                    <div className="flex bg-slate-700/50 rounded-lg p-0.5" title="Görünüm Modu">
                        <button
                            onClick={() => setViewMode('list')}
                            className={`p-1 rounded transition-colors ${viewMode === 'list' ? 'bg-slate-600 text-amber-400 shadow-sm' : 'text-slate-400 hover:text-slate-200'}`}
                        >
                            <List size={13} />
                        </button>
                        <button
                            onClick={() => setViewMode('paper')}
                            className={`p-1 rounded transition-colors ${viewMode === 'paper' ? 'bg-slate-600 text-amber-400 shadow-sm' : 'text-slate-400 hover:text-slate-200'}`}
                        >
                            <FileText size={13} />
                        </button>
                    </div>

                    {/* Font size */}
                    <div className="flex items-center gap-1 border-l border-slate-700 pl-3">
                        <Type size={12} className="text-slate-500" />
                        <button
                            onClick={() => setFontSize(Math.max(10, fontSize - 1))}
                            className="px-1 py-0.5 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition-colors"
                        >
                            A−
                        </button>
                        <span className="text-slate-300 font-mono w-5 text-center tabular-nums">{fontSize}</span>
                        <button
                            onClick={() => setFontSize(Math.min(40, fontSize + 1))}
                            className="px-1 py-0.5 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition-colors"
                        >
                            A+
                        </button>
                    </div>
                </div>

                {/* Error nav dropdown toggle */}
                <div className="relative">
                    <button
                        onClick={() => setShowErrors(!showErrors)}
                        className={`flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${showErrors
                            ? "text-amber-400 bg-slate-700"
                            : totalErrors > 0
                                ? "text-amber-400/80 hover:text-amber-400 hover:bg-slate-700"
                                : "text-slate-400 hover:text-white hover:bg-slate-700"
                            }`}
                    >
                        <AlertTriangle size={13} />
                        <span className="font-medium">Hatalar</span>
                        {totalErrors > 0 && (
                            <span className="bg-amber-500/20 text-amber-400 px-1.5 rounded-full text-[10px] font-bold tabular-nums">
                                {totalErrors}
                            </span>
                        )}
                        <ChevronRight size={12} className={`transition-transform ${showErrors ? "rotate-90" : ""}`} />
                    </button>

                    {/* Error dropdown panel */}
                    {showErrors && (
                        <div className="absolute right-0 top-full mt-1 w-56 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-50 p-2 space-y-1">
                            <ErrorNavBtn label="Gemini" count={errorGroups.gemini.length} onClick={() => jumpTo("gemini")} color="text-blue-400" />
                            <ErrorNavBtn label="GPT" count={errorGroups.openai.length} onClick={() => jumpTo("openai")} color="text-green-400" />
                            <ErrorNavBtn label="Claude" count={errorGroups.claude.length} onClick={() => jumpTo("claude")} color="text-orange-400" />
                            <div className="h-px bg-slate-700 my-1" />
                            <ErrorNavBtn label="GPT + Gemini" count={errorGroups.gptgem.length} onClick={() => jumpTo("gptgem")} color="text-teal-400" />
                            <ErrorNavBtn label="GPT + Claude" count={errorGroups.gptclaude.length} onClick={() => jumpTo("gptclaude")} color="text-yellow-400" />
                            <ErrorNavBtn label="3'ü Ortak" count={errorGroups.all3.length} onClick={() => jumpTo("all3")} color="text-red-400" />
                        </div>
                    )}
                </div>

                <div className="flex items-center gap-2 border-l border-slate-700 pl-3">
                    {editingSigla ? (
                        <div className="flex items-center gap-1">
                            <input
                                autoFocus
                                type="text"
                                value={tempSigla}
                                onChange={(e) => setTempSigla(e.target.value)}
                                className="w-8 h-5 text-center bg-slate-900 text-white text-xs border border-slate-600 rounded"
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                        updateSigla(nushaIndex, tempSigla);
                                        setEditingSigla(false);
                                    } else if (e.key === 'Escape') {
                                        setEditingSigla(false);
                                    }
                                }}
                                onBlur={() => {
                                    updateSigla(nushaIndex, tempSigla);
                                    setEditingSigla(false);
                                }}
                            />
                        </div>
                    ) : (
                        <button
                            onClick={() => {
                                setTempSigla(siglas[nushaIndex] || "");
                                setEditingSigla(true);
                            }}
                            className="text-xs font-bold text-slate-400 hover:text-white border border-slate-700 px-1.5 py-0.5 rounded bg-slate-800"
                            title="Rumuz Düzenle"
                        >
                            {siglas[nushaIndex] || (nushaIndex === 1 ? "A" : "B")}
                        </button>
                    )}

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
                                a.download = `project-${params.id}.docx`; // The browser might rename if backend provides Content-Disposition, but we set a default here.
                                // Actually, let's try to get filename from header if possible, but for now this is fine.
                                document.body.appendChild(a);
                                a.click();
                                window.URL.revokeObjectURL(url);
                                a.remove();
                            } catch (e: any) {
                                console.error('Export error:', e);
                                alert(`Word dosyası indirilemedi: ${e.message}`);
                            }
                        }}
                        className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-700"
                        title="Word Olarak İndir"
                    >
                        <Download size={14} />
                    </button>

                    {/* Settings Button */}
                    <button
                        onClick={() => setShowSettings(true)}
                        className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-700"
                        title="Ayarlar"
                    >
                        <Settings size={14} />
                    </button>
                </div>
            </div>

            {/* Expandable search row */}
            {showSearch && (
                <div className="flex items-center gap-2 px-3 py-1.5 border-t border-slate-700">
                    <div className="relative flex-1">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" size={13} />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Dizgide ara..."
                            autoFocus
                            className="w-full pl-8 pr-7 py-1.5 bg-slate-700 border border-slate-600 rounded-md text-slate-200 text-xs placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-amber-500/50 focus:border-amber-500/50"
                        />
                        {searchQuery && (
                            <button
                                onClick={() => setSearchQuery("")}
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                            >
                                <X size={12} />
                            </button>
                        )}
                    </div>
                    {searchQuery && (
                        <div className="flex items-center gap-1 text-[10px] text-slate-400 shrink-0">
                            <span className="tabular-nums">
                                {searchMatches.length > 0
                                    ? `${currentSearchIndex + 1}/${searchMatches.length}`
                                    : "0"}
                            </span>
                            <button onClick={prevSearch} disabled={!searchMatches.length} className="p-0.5 hover:bg-slate-700 rounded disabled:opacity-30"><ChevronUp size={14} /></button>
                            <button onClick={nextSearch} disabled={!searchMatches.length} className="p-0.5 hover:bg-slate-700 rounded disabled:opacity-30"><ChevronDown size={14} /></button>
                        </div>
                    )}
                </div>
            )}

            {/* Settings Modal */}
            {
                showSettings && (
                    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
                        <div className="bg-slate-800 border border-slate-600 rounded-lg shadow-2xl w-full max-w-sm animate-in fade-in zoom-in duration-200">
                            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
                                <h3 className="font-bold text-slate-200 text-sm flex items-center gap-2">
                                    <Settings size={16} />
                                    Proje Ayarları
                                </h3>
                                <button onClick={() => setShowSettings(false)} className="text-slate-400 hover:text-white hover:bg-slate-700 p-1 rounded transition-colors">
                                    <X size={16} />
                                </button>
                            </div>

                            <div className="p-4 space-y-4">
                                <div>
                                    <div className="text-xs font-bold text-slate-500 uppercase mb-3 px-1">Nüsha Yönetimi</div>
                                    <div className="space-y-2">
                                        {[1, 2, 3, 4].map(idx => (
                                            <div
                                                key={idx}
                                                className={`grid grid-cols-[1fr_auto_auto] gap-3 items-center p-2 rounded border transition-colors ${baseNushaIndex === idx
                                                    ? "bg-slate-700/80 border-amber-500/30 ring-1 ring-amber-500/20"
                                                    : "bg-slate-700/30 border-slate-700"
                                                    }`}
                                            >
                                                <div className="flex items-center gap-2">
                                                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${baseNushaIndex === idx ? "bg-amber-500 text-slate-900" : "bg-slate-600 text-slate-300"
                                                        }`}>
                                                        {idx}
                                                    </div>
                                                    <span className={`text-sm font-medium ${baseNushaIndex === idx ? "text-amber-100" : "text-slate-300"}`}>
                                                        Nüsha {idx}
                                                    </span>
                                                </div>

                                                {/* Sigla Input */}
                                                <div className="flex items-center gap-1.5" title="Rumuz">
                                                    <span className="text-[10px] uppercase font-bold text-slate-500">Rumuz</span>
                                                    <input
                                                        className="w-10 text-center bg-slate-900 border border-slate-600 rounded py-1 text-xs text-white uppercase placeholder-slate-600 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/50 transition-all font-mono"
                                                        placeholder={idx === 1 ? "A" : idx === 2 ? "B" : idx === 3 ? "C" : "D"}
                                                        defaultValue={siglas[idx] || ""}
                                                        onBlur={(e) => {
                                                            const val = e.target.value.trim().toUpperCase();
                                                            if (val !== (siglas[idx] || "")) {
                                                                updateSigla(idx, val);
                                                            }
                                                        }}
                                                        onKeyDown={(e) => {
                                                            if (e.key === "Enter") {
                                                                e.currentTarget.blur();
                                                            }
                                                        }}
                                                    />
                                                </div>

                                                {/* Base Nusha Radio */}
                                                <label className="flex items-center gap-1.5 cursor-pointer ml-1 pl-2 border-l border-slate-600/50" title="Asıl Nüsha Olarak Ayarla">
                                                    <input
                                                        type="radio"
                                                        name="baseNusha"
                                                        checked={baseNushaIndex === idx}
                                                        onChange={async () => {
                                                            await updateBaseNusha(idx);
                                                        }}
                                                        className="hidden peer"
                                                    />
                                                    <div className="w-3 h-3 rounded-full border border-slate-500 peer-checked:bg-amber-500 peer-checked:border-amber-500 transition-colors relative flex items-center justify-center">
                                                        <div className="w-1 h-1 bg-slate-900 rounded-full opacity-0 peer-checked:opacity-100 transition-opacity" />
                                                    </div>
                                                    <span className={`text-xs font-bold transition-colors ${baseNushaIndex === idx ? "text-amber-400" : "text-slate-500 peer-hover:text-slate-400"}`}>
                                                        ASIL
                                                    </span>
                                                </label>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div className="text-[10px] text-slate-500 bg-slate-700/30 p-2 rounded border border-slate-700/50 flex align-top gap-2">
                                    <AlertTriangle size={12} className="text-amber-500/70 mt-0.5 shrink-0" />
                                    <span>
                                        <strong className="text-slate-400">Not:</strong> Asıl Nüsha değişimi, ana metin görünümünü ve dipnot referanslarını doğrudan etkiler.
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                )
            }
        </div >
    );
}

function ErrorNavBtn({ label, count, onClick, color }: { label: string; count: number; onClick: () => void; color: string }) {
    return (
        <button
            onClick={onClick}
            disabled={count === 0}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-xs"
        >
            <span className={`font-medium ${color}`}>{label}</span>
            <span className="bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded-full text-[10px] font-bold tabular-nums min-w-[1.5rem] text-center">
                {count}
            </span>
        </button>
    );
}
