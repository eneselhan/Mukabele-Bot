"use client";

import React from "react";
import { useMukabele } from "./MukabeleContext";
import { useTTS } from "./TTSContext";
import {
    ZoomIn, ZoomOut,
    Type, Monitor,
    Play, Pause, Square, FastForward,
    ChevronLeft, ChevronRight,
    Volume2, RefreshCw
} from "lucide-react";

export default function ControlBar() {
    const {
        zoom, setZoom,
        fontSize, setFontSize,
        activeLine,
        activePageKey, setActivePageKey,
        pages,
        nushaIndex, setNushaIndex,
        data
    } = useMukabele();
    const nextPage = () => {
        if (!activePageKey || pages.length === 0) return;
        const idx = pages.findIndex(p => p.key === activePageKey);
        if (idx < pages.length - 1) {
            setActivePageKey(pages[idx + 1].key);
        }
    };

    const prevPage = () => {
        if (!activePageKey || pages.length === 0) return;
        const idx = pages.findIndex(p => p.key === activePageKey);
        if (idx > 0) {
            setActivePageKey(pages[idx - 1].key);
        }
    };
    const { isPlaying, isLoading, play, pause, stop, rate, setRate } = useTTS();

    if (!data) return null;

    return (
        <div className="flex items-center gap-4 bg-white border-b border-slate-200 px-4 py-2 shadow-sm text-sm">
            {/* Page Navigation */}
            <div className="flex items-center gap-2 border-l pl-4 ml-2 border-slate-700">
                <button
                    onClick={prevPage}
                    disabled={!activePageKey || pages.findIndex(p => p.key === activePageKey) <= 0}
                    className="p-1.5 text-slate-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                    title="Önceki Sayfa"
                >
                    <ChevronLeft size={20} />
                </button>

                <span className="text-sm font-medium min-w-[3rem] text-center">
                    {activePageKey && pages.length > 0 ? (
                        <>
                            {pages.findIndex(p => p.key === activePageKey) + 1} / {pages.length}
                        </>
                    ) : (
                        "- / -"
                    )}
                </span>

                <button
                    onClick={nextPage}
                    disabled={!activePageKey || pages.findIndex(p => p.key === activePageKey) >= pages.length - 1}
                    className="p-1.5 text-slate-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                    title="Sonraki Sayfa"
                >
                    <ChevronRight size={20} />
                </button>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center gap-1 border-r pr-4">
                <span className="text-slate-500 mr-2 flex items-center gap-1"><ZoomIn size={14} /> Zoom</span>
                <button onClick={() => setZoom(zoom - 0.1)} className="p-1 hover:bg-slate-100 rounded">-</button>
                <span className="w-12 text-center font-mono">{Math.round(zoom * 100)}%</span>
                <button onClick={() => setZoom(zoom + 0.1)} className="p-1 hover:bg-slate-100 rounded">+</button>
                <button onClick={() => setZoom(1.32)} className="text-xs text-blue-600 hover:underline ml-1">Sıfırla</button>
            </div>

            {/* Font Size Controls */}
            <div className="flex items-center gap-1 border-r pr-4">
                <span className="text-slate-500 mr-2 flex items-center gap-1"><Type size={14} /> Punto</span>
                <button onClick={() => setFontSize(fontSize - 1)} className="p-1 hover:bg-slate-100 rounded">A-</button>
                <span className="w-8 text-center font-mono">{fontSize}</span>
                <button onClick={() => setFontSize(fontSize + 1)} className="p-1 hover:bg-slate-100 rounded">A+</button>
            </div>

            {/* Voice Controls */}
            <div className="flex items-center gap-1 border-r pr-4">
                <span className="text-slate-500 mr-2 flex items-center gap-1"><Volume2 size={14} /> Ses</span>
                <button
                    onClick={isPlaying ? pause : play}
                    disabled={isLoading}
                    className={`p-1.5 rounded-full hover:bg-slate-100 disabled:opacity-50 ${isPlaying ? 'text-red-600' : 'text-green-600'}`}
                    title={isPlaying ? "Duraklat" : "Seslendir"}
                >
                    {isLoading ? <RefreshCw className="animate-spin" size={16} /> : (isPlaying ? <Pause size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />)}
                </button>

                {isPlaying && (
                    <button onClick={stop} className="p-1.5 hover:bg-slate-100 text-slate-500 rounded-full" title="Durdur">
                        <Square size={14} fill="currentColor" />
                    </button>
                )}

                <select
                    value={rate}
                    onChange={(e) => setRate(parseFloat(e.target.value))}
                    className="text-xs bg-slate-50 border border-slate-200 rounded px-1 py-0.5 ml-1 h-6 outline-none"
                >
                    <option value={0.75}>0.75x</option>
                    <option value={1.0}>1.0x</option>
                    <option value={1.25}>1.25x</option>
                    <option value={1.5}>1.5x</option>
                </select>
            </div>

            {/* Nusha Selection */}
            <div className="flex items-center gap-2">
                <span className="text-slate-500 flex items-center gap-1"><Monitor size={14} /> Nüsha:</span>

                <button
                    onClick={() => setNushaIndex(1)}
                    className={`px-3 py-1 rounded-full border transition-colors ${nushaIndex === 1 ? "bg-slate-800 text-white border-slate-800" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                        }`}
                >
                    Nüsha 1
                </button>

                {data.has_alt && (
                    <button
                        onClick={() => setNushaIndex(2)}
                        className={`px-3 py-1 rounded-full border transition-colors ${nushaIndex === 2 ? "bg-slate-800 text-white border-slate-800" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                            }`}
                    >
                        Nüsha 2
                    </button>
                )}

                {data.has_alt3 && (
                    <button
                        onClick={() => setNushaIndex(3)}
                        className={`px-3 py-1 rounded-full border transition-colors ${nushaIndex === 3 ? "bg-slate-800 text-white border-slate-800" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                            }`}
                    >
                        Nüsha 3
                    </button>
                )}

                {data.has_alt4 && (
                    <button
                        onClick={() => setNushaIndex(4)}
                        className={`px-3 py-1 rounded-full border transition-colors ${nushaIndex === 4 ? "bg-slate-800 text-white border-slate-800" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                            }`}
                    >
                        Nüsha 4
                    </button>
                )}
            </div>
        </div>
    );
}
