"use client";

import React from "react";
import { Settings, X, AlertTriangle } from "lucide-react";
import { useMukabele } from "./MukabeleContext";

interface ProjectSettingsDialogProps {
    isOpen: boolean;
    onClose: () => void;
}

export default function ProjectSettingsDialog({ isOpen, onClose }: ProjectSettingsDialogProps) {
    const {
        siglas, updateSigla,
        baseNushaIndex, updateBaseNusha
    } = useMukabele();

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
            <div className="bg-slate-800 border border-slate-600 rounded-lg shadow-2xl w-full max-w-sm animate-in fade-in zoom-in duration-200">
                <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
                    <h3 className="font-bold text-slate-200 text-sm flex items-center gap-2">
                        <Settings size={16} />
                        Proje Ayarları
                    </h3>
                    <button onClick={onClose} className="text-slate-400 hover:text-white hover:bg-slate-700 p-1 rounded transition-colors">
                        <X size={16} />
                    </button>
                </div>

                <div className="p-4 space-y-4">
                    <div>
                        <div className="text-xs font-bold text-slate-500 uppercase mb-3 px-1">Nüsha Yönetimi</div>
                        <div className="space-y-2">
                            {[1, 2, 3, 4].map(idx => (
                                <div
                                    key={idx}
                                    className={`grid grid-cols-[1fr_auto_auto] gap-3 items-center p-2 rounded border transition-colors ${baseNushaIndex === idx
                                        ? "bg-slate-700/80 border-amber-500/30 ring-1 ring-amber-500/20"
                                        : "bg-slate-700/30 border-slate-700"
                                        }`}
                                >
                                    <div className="flex items-center gap-2">
                                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${baseNushaIndex === idx ? "bg-amber-500 text-slate-900" : "bg-slate-600 text-slate-300"
                                            }`}>
                                            {idx}
                                        </div>
                                        <span className={`text-sm font-medium ${baseNushaIndex === idx ? "text-amber-100" : "text-slate-300"}`}>
                                            Nüsha {idx}
                                        </span>
                                    </div>

                                    {/* Sigla Input */}
                                    <div className="flex items-center gap-1.5" title="Rumuz">
                                        <span className="text-[10px] uppercase font-bold text-slate-500">Rumuz</span>
                                        <input
                                            className="w-10 text-center bg-slate-900 border border-slate-600 rounded py-1 text-xs text-white uppercase placeholder-slate-600 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/50 transition-all font-mono"
                                            placeholder={idx === 1 ? "A" : idx === 2 ? "B" : idx === 3 ? "C" : "D"}
                                            defaultValue={siglas[idx] || ""}
                                            onBlur={(e) => {
                                                const val = e.target.value.trim().toUpperCase();
                                                if (val !== (siglas[idx] || "")) {
                                                    updateSigla(idx, val);
                                                }
                                            }}
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter") {
                                                    e.currentTarget.blur();
                                                }
                                            }}
                                        />
                                    </div>

                                    {/* Base Nusha Radio */}
                                    <label className="flex items-center gap-1.5 cursor-pointer ml-1 pl-2 border-l border-slate-600/50" title="Asıl Nüsha Olarak Ayarla">
                                        <input
                                            type="radio"
                                            name="baseNusha"
                                            checked={baseNushaIndex === idx}
                                            onChange={async () => {
                                                await updateBaseNusha(idx);
                                            }}
                                            className="hidden peer"
                                        />
                                        <div className="w-3 h-3 rounded-full border border-slate-500 peer-checked:bg-amber-500 peer-checked:border-amber-500 transition-colors relative flex items-center justify-center">
                                            <div className="w-1 h-1 bg-slate-900 rounded-full opacity-0 peer-checked:opacity-100 transition-opacity" />
                                        </div>
                                        <span className={`text-xs font-bold transition-colors ${baseNushaIndex === idx ? "text-amber-400" : "text-slate-500 peer-hover:text-slate-400"}`}>
                                            ASIL
                                        </span>
                                    </label>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="text-[10px] text-slate-500 bg-slate-700/30 p-2 rounded border border-slate-700/50 flex align-top gap-2">
                        <AlertTriangle size={12} className="text-amber-500/70 mt-0.5 shrink-0" />
                        <span>
                            <strong className="text-slate-400">Not:</strong> Asıl Nüsha değişimi, ana metin görünümünü ve dipnot referanslarını doğrudan etkiler.
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}
