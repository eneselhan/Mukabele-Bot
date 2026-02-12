"use client";

import React, { useState, useMemo } from "react";
import { useMukabele } from "./MukabeleContext";
import {
    Search, X, ChevronUp, ChevronDown,
    Type, AlertTriangle, ChevronRight,
    List, FileText
} from "lucide-react";

export default function TextPanelToolbar() {
    const {
        fontSize, setFontSize,
        searchQuery, setSearchQuery,
        searchMatches, currentSearchIndex,
        nextSearch, prevSearch,
        lines, setActiveLine,
        viewMode, setViewMode
    } = useMukabele();

    const [showSearch, setShowSearch] = useState(false);
    const [showErrors, setShowErrors] = useState(false);
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
        </div>
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
