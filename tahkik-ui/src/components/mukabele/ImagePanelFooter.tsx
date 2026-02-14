"use client";

import React from "react";
import { useTTS } from "./TTSContext";
import { Play, Pause, Square, RefreshCw, Keyboard } from "lucide-react";

export default function ImagePanelFooter() {
    return (
        <div className="flex items-center justify-end px-3 py-1.5 bg-white border-t border-slate-200 text-xs shrink-0 h-[72px]">
            {/* TTS Controls */}
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
