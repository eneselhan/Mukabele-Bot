"use client";

import React from "react";
import { X } from "lucide-react";

interface ErrorDetailModalProps {
    isOpen: boolean;
    onClose: () => void;
    errorMeta: {
        wrong: string;
        suggestion: string;
        reason: string;
        sources: string[];
        paragraph_index?: number;
    } | null;
}

export default function ErrorDetailModal({ isOpen, onClose, errorMeta }: ErrorDetailModalProps) {
    if (!isOpen || !errorMeta) return null;

    // Close on Escape key
    React.useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };

        if (isOpen) {
            document.addEventListener("keydown", handleEscape);
            return () => document.removeEventListener("keydown", handleEscape);
        }
    }, [isOpen, onClose]);

    return (
        <div
            className="fixed inset-0 bg-black/25 z-[1120] flex items-center justify-center p-4"
            onClick={onClose}
        >
            <div
                className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[520px] overflow-auto border border-slate-200"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-slate-50 rounded-t-2xl">
                    <h3 className="font-black text-slate-800">İmla Hatası Detayı</h3>
                    <button
                        onClick={onClose}
                        className="p-1 hover:bg-slate-200 rounded-full transition-colors"
                        title="Kapat (ESC)"
                    >
                        <X size={20} className="text-slate-600" />
                    </button>
                </div>

                {/* Body */}
                <div className="flex flex-col gap-3 p-4">
                    {/* Wrong Word */}
                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                        <div className="font-extrabold text-slate-700 mb-2">Hatalı</div>
                        <div
                            className="text-lg font-arabic direction-rtl"
                            style={{
                                fontFamily: '"Traditional Arabic", "Noto Naskh Arabic", "Amiri", "Scheherazade New", "Geeza Pro", serif',
                                direction: 'rtl',
                                unicodeBidi: 'isolate'
                            }}
                        >
                            {errorMeta.wrong}
                        </div>
                    </div>

                    {/* Suggestion */}
                    {errorMeta.suggestion && (
                        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                            <div className="font-extrabold text-slate-700 mb-2">Öneri</div>
                            <div
                                className="text-lg font-arabic"
                                style={{
                                    fontFamily: '"Traditional Arabic", "Noto Naskh Arabic", "Amiri", "Scheherazade New", "Geeza Pro", serif',
                                    direction: 'rtl',
                                    unicodeBidi: 'isolate'
                                }}
                            >
                                {errorMeta.suggestion}
                            </div>
                        </div>
                    )}

                    {/* Reason */}
                    {errorMeta.reason ? (
                        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                            <div className="font-extrabold text-slate-700 mb-2">Açıklama</div>
                            <div
                                className="text-base leading-relaxed font-arabic"
                                style={{
                                    fontFamily: '"Traditional Arabic", "Noto Naskh Arabic", "Amiri", "Scheherazade New", "Geeza Pro", serif',
                                    direction: 'rtl',
                                    unicodeBidi: 'isolate'
                                }}
                            >
                                {errorMeta.reason}
                            </div>
                        </div>
                    ) : (
                        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                            <div className="font-extrabold text-slate-700 mb-2">Açıklama</div>
                            <div className="text-sm text-slate-400">
                                Bu hata için açıklama yok.
                            </div>
                        </div>
                    )}

                    {/* Metadata (Sources + Paragraph) */}
                    {(errorMeta.sources.length > 0 || errorMeta.paragraph_index) && (
                        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                            <div className="font-extrabold text-slate-700 mb-2">Bilgi</div>
                            <div className="text-sm text-slate-600 space-y-1">
                                {errorMeta.paragraph_index && (
                                    <div>
                                        Paragraf: <span className="font-bold">{errorMeta.paragraph_index}</span>
                                    </div>
                                )}
                                {errorMeta.sources.length > 0 && (
                                    <div>
                                        Kaynak: <span className="font-bold">{errorMeta.sources.join(", ")}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
