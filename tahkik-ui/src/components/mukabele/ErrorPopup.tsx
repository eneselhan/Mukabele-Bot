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
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
            onClick={() => setErrorPopupData(null)}
        >
            <div
                className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden border border-slate-200"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b bg-slate-50">
                    <h3 className="font-bold text-slate-800">İmla Hatası Detayı</h3>
                    <button
                        onClick={() => setErrorPopupData(null)}
                        className="p-1 hover:bg-slate-200 rounded-full transition-colors"
                    >
                        <X size={18} className="text-slate-500" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-4 flex flex-col gap-3 max-h-[80vh] overflow-y-auto">

                    {/* Wrong */}
                    <div className="bg-red-50 border border-red-100 rounded-lg p-3">
                        <div className="text-xs font-bold text-red-500 uppercase mb-1">Hatalı Kelime</div>
                        <div className="text-lg font-serif dir-rtl">{wrong}</div>
                    </div>

                    {/* Suggestion */}
                    {suggestion && (
                        <div className="bg-green-50 border border-green-100 rounded-lg p-3">
                            <div className="text-xs font-bold text-green-600 uppercase mb-1">Öneri</div>
                            <div className="text-lg font-serif dir-rtl">{suggestion}</div>
                        </div>
                    )}

                    {/* Reason */}
                    <div className="bg-slate-50 border border-slate-100 rounded-lg p-3">
                        <div className="text-xs font-bold text-slate-500 uppercase mb-1">Açıklama</div>
                        <div className="text-base font-serif dir-rtl leading-relaxed text-slate-700">
                            {reason || <span className="text-slate-400 italic">Açıklama yok.</span>}
                        </div>
                    </div>

                    {/* Metadata */}
                    <div className="flex flex-wrap gap-2 text-xs text-slate-500 mt-2">
                        {paragraph_index !== undefined && (
                            <span className="px-2 py-1 bg-slate-100 rounded border border-slate-200">
                                Paragraf: {paragraph_index}
                            </span>
                        )}
                        {sources && Array.isArray(sources) && sources.map((src: string) => (
                            <span key={src} className="px-2 py-1 bg-blue-50 text-blue-600 rounded border border-blue-100 uppercase">
                                {src}
                            </span>
                        ))}
                    </div>

                </div>
            </div>
        </div>
    );
}
