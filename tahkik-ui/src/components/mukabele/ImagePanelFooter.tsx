"use client";

import React from "react";
import { useTTS } from "./TTSContext";
import { Play, Pause, Square, RefreshCw, Keyboard } from "lucide-react";

export default function ImagePanelFooter() {
    const { isPlaying, isLoading, play, pause, stop, rate, setRate } = useTTS();

    return (
        <div className="flex items-center justify-between px-3 py-1.5 bg-white border-t border-slate-200 text-xs shrink-0">
            {/* TTS Controls */}
            <div className="flex items-center gap-2">
                <span className="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Ses</span>

                <button
                    onClick={isPlaying ? pause : play}
                    disabled={isLoading}
                    className={`p-1.5 rounded-full transition-colors disabled:opacity-50 ${isPlaying
                        ? "text-red-500 bg-red-50 hover:bg-red-100"
                        : "text-emerald-500 bg-emerald-50 hover:bg-emerald-100"
                        }`}
                    title={isPlaying ? "Duraklat (Space)" : "Seslendir (Space)"}
                >
                    {isLoading
                        ? <RefreshCw className="animate-spin" size={14} />
                        : isPlaying
                            ? <Pause size={14} fill="currentColor" />
                            : <Play size={14} fill="currentColor" />
                    }
                </button>

                {isPlaying && (
                    <button
                        onClick={stop}
                        className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition-colors"
                        title="Durdur"
                    >
                        <Square size={12} fill="currentColor" />
                    </button>
                )}

                <select
                    value={rate}
                    onChange={(e) => setRate(parseFloat(e.target.value))}
                    className="bg-slate-100 border border-slate-200 text-slate-600 rounded px-1.5 py-0.5 text-[10px] outline-none cursor-pointer hover:border-slate-300 transition-colors"
                >
                    <option value={0.75}>0.75×</option>
                    <option value={1.0}>1.0×</option>
                    <option value={1.25}>1.25×</option>
                    <option value={1.5}>1.5×</option>
                </select>
            </div>

            {/* Keyboard hints */}
            <div className="hidden md:flex items-center gap-2 text-[10px] text-slate-500">
                <div className="flex items-center gap-1" title="Klavye Kısayolları">
                    <Keyboard size={12} className="text-slate-400" />
                </div>
                <div className="flex items-center gap-1">
                    <kbd className="px-1 py-0.5 bg-slate-100 border border-slate-200 rounded text-slate-500 font-sans">↑↓</kbd>
                    <span className="text-slate-400">satır</span>
                </div>
                <div className="flex items-center gap-1">
                    <kbd className="px-1 py-0.5 bg-slate-100 border border-slate-200 rounded text-slate-500 font-sans">←→</kbd>
                    <span className="text-slate-400">sayfa</span>
                </div>
                <div className="flex items-center gap-1">
                    <kbd className="px-1 py-0.5 bg-slate-100 border border-slate-200 rounded text-slate-500 font-sans">E</kbd>
                    <span className="text-slate-400">hata</span>
                </div>
            </div>
        </div>
    );
}
