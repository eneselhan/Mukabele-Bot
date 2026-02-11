"use client";

import React from "react";
import { useMukabele } from "./MukabeleContext";
import { X } from "lucide-react";

export default function ErrorPopup() {
    const { errorPopupData, setErrorPopupData } = useMukabele();

    if (!errorPopupData) return null;

    const { wrong, suggestion, reason, sources, paragraph_index } = errorPopupData;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
            onClick={() => setErrorPopupData(null)}
        >
            <div
                className="bg-slate-800 rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden border border-slate-700"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-900">
                    <h3 className="font-bold text-slate-200">İmla Hatası Detayı</h3>
                    <button
                        onClick={() => setErrorPopupData(null)}
                        className="p-1 hover:bg-slate-700 rounded-full transition-colors"
                    >
                        <X size={18} className="text-slate-400" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-4 flex flex-col gap-3 max-h-[80vh] overflow-y-auto">
                    {/* Wrong */}
                    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                        <div className="text-xs font-bold text-red-400 uppercase mb-1">Hatalı Kelime</div>
                        <div className="text-lg font-serif text-red-300" dir="rtl">{wrong}</div>
                    </div>

                    {/* Suggestion */}
                    {suggestion && (
                        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
                            <div className="text-xs font-bold text-emerald-400 uppercase mb-1">Öneri</div>
                            <div className="text-lg font-serif text-emerald-300" dir="rtl">{suggestion}</div>
                        </div>
                    )}

                    {/* Reason */}
                    <div className="bg-slate-700/50 border border-slate-600 rounded-lg p-3">
                        <div className="text-xs font-bold text-slate-400 uppercase mb-1">Açıklama</div>
                        <div className="text-base font-serif leading-relaxed text-slate-300" dir="rtl">
                            {reason || <span className="text-slate-500 italic">Açıklama yok.</span>}
                        </div>
                    </div>

                    {/* Metadata */}
                    <div className="flex flex-wrap gap-2 text-xs mt-1">
                        {paragraph_index !== undefined && (
                            <span className="px-2 py-1 bg-slate-700 rounded border border-slate-600 text-slate-400">
                                Paragraf: {paragraph_index}
                            </span>
                        )}
                        {sources && Array.isArray(sources) && sources.map((src: string) => (
                            <span key={src} className="px-2 py-1 bg-blue-500/10 text-blue-400 rounded border border-blue-500/20 uppercase font-bold">
                                {src}
                            </span>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
