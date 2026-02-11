"use client";

import React from "react";
import { useMukabele } from "./MukabeleContext";
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";

export default function ImagePanelToolbar() {
    const {
        zoom, setZoom,
        activePageKey, setActivePageKey,
        pages
    } = useMukabele();

    const pageIdx = pages.findIndex(p => p.key === activePageKey);

    const nextPage = () => {
        if (pageIdx < pages.length - 1) setActivePageKey(pages[pageIdx + 1].key);
    };
    const prevPage = () => {
        if (pageIdx > 0) setActivePageKey(pages[pageIdx - 1].key);
    };

    return (
        <div className="flex items-center justify-between px-3 py-1.5 bg-slate-800 border-b border-slate-700 text-xs shrink-0">
            {/* Page Navigation */}
            <div className="flex items-center gap-1.5">
                <button
                    onClick={prevPage}
                    disabled={pageIdx <= 0}
                    className="p-1 text-slate-300 hover:text-white hover:bg-slate-700 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    title="Önceki Sayfa (←)"
                >
                    <ChevronLeft size={16} />
                </button>
                <span className="text-slate-300 font-medium min-w-[4rem] text-center tabular-nums">
                    {pages.length > 0 ? `Sayfa ${pageIdx + 1} / ${pages.length}` : "—"}
                </span>
                <button
                    onClick={nextPage}
                    disabled={pageIdx >= pages.length - 1}
                    className="p-1 text-slate-300 hover:text-white hover:bg-slate-700 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    title="Sonraki Sayfa (→)"
                >
                    <ChevronRight size={16} />
                </button>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center gap-1">
                <ZoomOut size={13} className="text-slate-500" />
                <button
                    onClick={() => setZoom(Math.max(0.3, zoom - 0.1))}
                    className="px-1.5 py-0.5 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition-colors font-bold"
                >
                    −
                </button>
                <span className="text-slate-300 font-mono w-10 text-center tabular-nums">
                    {Math.round(zoom * 100)}%
                </span>
                <button
                    onClick={() => setZoom(Math.min(3, zoom + 0.1))}
                    className="px-1.5 py-0.5 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition-colors font-bold"
                >
                    +
                </button>
                <ZoomIn size={13} className="text-slate-500" />
                <button
                    onClick={() => setZoom(1.0)}
                    className="ml-1 p-1 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
                    title="Sıfırla"
                >
                    <RotateCcw size={12} />
                </button>
            </div>
        </div>
    );
}
