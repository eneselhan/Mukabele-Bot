"use client";

import React from "react";
import { useTTS } from "./TTSContext";
import { Play, Pause, Square, RefreshCw, Volume2 } from "lucide-react";

export default function TextPanelFooter() {
    const {
        isPlaying, isLoading, play, pause, stop,
        rate, setRate,
        currentTime, duration, seek
    } = useTTS();

    const formatTime = (t: number) => {
        if (!t || isNaN(t)) return "00:00";
        const m = Math.floor(t / 60);
        const s = Math.floor(t % 60);
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    };

    return (
        <div className="flex flex-col px-3 py-2 bg-white border-t border-slate-200 text-xs shrink-0 gap-2 w-full">
            {/* Scrubber Row */}
            <div className="flex items-center gap-3 w-full">
                <span className="text-[10px] text-slate-500 font-mono tabular-nums w-8 text-right">
                    {formatTime(currentTime)}
                </span>
                <div className="flex-1 flex items-center h-4 relative">
                    <input
                        type="range"
                        min={0}
                        max={duration || 0.1}
                        step={0.1}
                        value={currentTime}
                        onChange={(e) => seek(parseFloat(e.target.value))}
                        className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                        disabled={!duration}
                    />
                </div>
                <span className="text-[10px] text-slate-500 font-mono tabular-nums w-8">
                    {formatTime(duration)}
                </span>
            </div>

            {/* Controls Row */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <button
                        onClick={isPlaying ? pause : play}
                        disabled={isLoading}
                        className={`p-1.5 rounded-full transition-colors flex items-center gap-1.5 px-3 ${isPlaying
                            ? "text-red-600 bg-red-50 hover:bg-red-100"
                            : "text-emerald-600 bg-emerald-50 hover:bg-emerald-100"
                            }`}
                        title={isPlaying ? "Duraklat" : "Seslendir"}
                    >
                        {isLoading
                            ? <RefreshCw className="animate-spin" size={14} />
                            : isPlaying
                                ? <><Pause size={14} fill="currentColor" /><span className="font-semibold text-[10px]">DURAKLAT</span></>
                                : <><Play size={14} fill="currentColor" /><span className="font-semibold text-[10px]">OKU</span></>
                        }
                    </button>

                    {isPlaying && (
                        <button
                            onClick={stop}
                            className="p-1.5 text-slate-500 hover:text-red-700 hover:bg-red-50 rounded-full transition-colors"
                            title="Durdur"
                        >
                            <Square size={12} fill="currentColor" />
                        </button>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 text-slate-400">
                        <Volume2 size={12} />
                    </div>
                    <select
                        value={rate}
                        onChange={(e) => setRate(parseFloat(e.target.value))}
                        className="bg-slate-50 border border-slate-200 text-slate-600 rounded px-1.5 py-0.5 text-[10px] outline-none cursor-pointer hover:border-slate-300 transition-colors"
                    >
                        <option value={0.75}>0.75×</option>
                        <option value={1.0}>1.0×</option>
                        <option value={1.25}>1.25×</option>
                        <option value={1.5}>1.5×</option>
                        <option value={2.0}>2.0×</option>
                    </select>
                </div>
            </div>
        </div>
    );
}
