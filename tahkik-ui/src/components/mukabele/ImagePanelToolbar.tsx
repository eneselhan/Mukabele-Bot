"use client";

import React, { useState } from "react";
import { useMukabele } from "./MukabeleContext";
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, RotateCcw, Settings } from "lucide-react";
import ProjectSettingsDialog from "./ProjectSettingsDialog";

export default function ImagePanelToolbar() {
    const {
        zoom, setZoom,
        activePageKey, setActivePageKey,
        pages,
        nushaIndex, setNushaIndex,
        siglas,
        data // Need data for Nusha availability check
    } = useMukabele();

    const [showSettings, setShowSettings] = useState(false);

    const pageIdx = pages.findIndex(p => p.key === activePageKey);

    const nextPage = () => {
        if (pageIdx < pages.length - 1) setActivePageKey(pages[pageIdx + 1].key);
    };
    const prevPage = () => {
        if (pageIdx > 0) setActivePageKey(pages[pageIdx - 1].key);
    };

    return (
        <div className="flex items-center justify-between px-3 py-1.5 bg-white border-b border-slate-200 text-xs shrink-0">
            <ProjectSettingsDialog isOpen={showSettings} onClose={() => setShowSettings(false)} />

            {/* Left: Nüsha Selection & Settings */}
            <div className="flex items-center gap-3">
                {/* Settings Button */}
                <button
                    onClick={() => setShowSettings(true)}
                    className="p-1 rounded transition-colors text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                    title="Proje Ayarları"
                >
                    <Settings size={14} />
                </button>

                <div className="h-4 w-px bg-slate-200" />

                {/* Nüsha Toggle */}
                <div className="flex items-center bg-slate-100 rounded-lg p-0.5">
                    {[1, 2, 3, 4].map(idx => {
                        // Check availability if data is loaded
                        let hasNusha = false;
                        if (idx === 1) hasNusha = true;
                        else if (data) {
                            if (idx === 2) hasNusha = !!data.has_alt;
                            if (idx === 3) hasNusha = !!data.has_alt3;
                            if (idx === 4) hasNusha = !!data.has_alt4;
                        }

                        if (!hasNusha) return null;

                        const sigla = siglas[idx] || (idx === 1 ? "A" : idx === 2 ? "B" : idx === 3 ? "C" : "D");

                        return (
                            <button
                                key={idx}
                                onClick={() => setNushaIndex(idx)}
                                className={`
                                    px-2 py-0.5 rounded-md text-[10px] font-bold transition-all
                                    ${nushaIndex === idx
                                        ? "bg-white text-amber-600 shadow-sm ring-1 ring-black/5"
                                        : "text-slate-400 hover:text-slate-600 hover:bg-slate-200/50"
                                    }
                                `}
                                title={`${sigla} Nüshası`}
                            >
                                {sigla}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Right: Page Nav & Zoom */}
            <div className="flex items-center gap-4">
                {/* Page Navigation */}
                <div className="flex items-center gap-1.5 border-r border-slate-200 pr-3">
                    <button
                        onClick={prevPage}
                        disabled={pageIdx <= 0}
                        className="p-1 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title="Önceki Sayfa (←)"
                    >
                        <ChevronLeft size={16} />
                    </button>
                    <span className="text-slate-600 font-medium min-w-[3.5rem] text-center tabular-nums">
                        {pages.length > 0 ? `${pageIdx + 1} / ${pages.length}` : "-"}
                    </span>
                    <button
                        onClick={nextPage}
                        disabled={pageIdx >= pages.length - 1}
                        className="p-1 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title="Sonraki Sayfa (→)"
                    >
                        <ChevronRight size={16} />
                    </button>
                </div>

                {/* Zoom Controls */}
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => setZoom(Math.max(0.3, zoom - 0.1))}
                        className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
                    >
                        <ZoomOut size={13} />
                    </button>
                    <span className="text-slate-500 font-mono w-9 text-center tabular-nums text-[10px]">
                        {Math.round(zoom * 100)}%
                    </span>
                    <button
                        onClick={() => setZoom(Math.min(3, zoom + 0.1))}
                        className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
                    >
                        <ZoomIn size={13} />
                    </button>
                </div>
            </div>
        </div>
    );
}
