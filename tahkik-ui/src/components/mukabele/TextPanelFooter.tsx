"use client";

import React from "react";
import { useTTS } from "./TTSContext";
import { Play, Pause, Square, RefreshCw } from "lucide-react";

export default function TextPanelFooter() {
    const { isPlaying, isLoading, play, pause, stop, rate, setRate } = useTTS();

    return (
        <div className="flex items-center justify-between px-3 py-1.5 bg-slate-800 border-t border-slate-700 text-xs shrink-0">
            {/* TTS Controls */}
            <div className="flex items-center gap-2">
                <span className="text-slate-500 text-[10px] font-bold uppercase tracking-wider">Ses</span>

                <button
                    onClick={isPlaying ? pause : play}
                    disabled={isLoading}
                    className={`p-1.5 rounded-full transition-colors disabled:opacity-50 ${isPlaying
                        ? "text-red-400 bg-red-500/10 hover:bg-red-500/20"
                        : "text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20"
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
                        className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded-full transition-colors"
                        title="Durdur"
                    >
                        <Square size={12} fill="currentColor" />
                    </button>
                )}

                <select
                    value={rate}
                    onChange={(e) => setRate(parseFloat(e.target.value))}
                    className="bg-slate-700 border border-slate-600 text-slate-300 rounded px-1.5 py-0.5 text-[10px] outline-none cursor-pointer hover:border-slate-500 transition-colors"
                >
                    <option value={0.75}>0.75×</option>
                    <option value={1.0}>1.0×</option>
                    <option value={1.25}>1.25×</option>
                    <option value={1.5}>1.5×</option>
                </select>
            </div>

            {/* Keyboard hints */}
            <div className="hidden md:flex items-center gap-2 text-[10px] text-slate-600">
                <kbd className="px-1 py-0.5 bg-slate-700 border border-slate-600 rounded text-slate-400">↑↓</kbd>
                <span className="text-slate-500">satır</span>
                <kbd className="px-1 py-0.5 bg-slate-700 border border-slate-600 rounded text-slate-400">←→</kbd>
                <span className="text-slate-500">sayfa</span>
                <kbd className="px-1 py-0.5 bg-slate-700 border border-slate-600 rounded text-slate-400">E</kbd>
                <span className="text-slate-500">hata</span>
            </div>
        </div>
    );
}
