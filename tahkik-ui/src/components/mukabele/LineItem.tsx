"use client";

import React, { useState, useRef, useEffect } from "react";
import { highlightTextArabic } from "./utils";
import { Save, Check, AlertTriangle, Pencil, Trash2 } from "lucide-react";
import { LineData, useMukabele } from "./MukabeleContext";
import { useTTS } from "./TTSContext";
import { useParams } from "next/navigation";

interface LineItemProps {
    line: LineData;
    isActive: boolean;
    onSelect: () => void;
    fontSize: number;
}

export default function LineItem({ line, isActive, onSelect, fontSize }: LineItemProps) {
    const params = useParams();
    const projectId = params.id as string;
    const { setErrorPopupData, nushaIndex, updateLineText, deleteLine } = useMukabele();
    const { activeWordIndex } = useTTS();

    const [isSaving, setIsSaving] = useState(false);
    const [isEdited, setIsEdited] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const contentRef = useRef<HTMLPreElement>(null);
    const [htmlContent, setHtmlContent] = useState("");

    // Determine line status
    const hasErrors = line.line_marks && line.line_marks.length > 0;
    const statusIcon = isEdited
        ? <Pencil size={11} className="text-blue-400" />
        : hasErrors
            ? <AlertTriangle size={11} className="text-amber-400" />
            : <Check size={11} className="text-emerald-500" />;

    useEffect(() => {
        const raw = line.best?.raw || "";
        const start = line.best?.start_word || 0;
        const marks = line.line_marks || [];
        setHtmlContent(highlightTextArabic(raw, start, marks, activeWordIndex));
    }, [line, activeWordIndex]);

    const saveText = async (newText: string) => {
        if (isSaving) return;
        setIsSaving(true);
        try {
            const res = await fetch(`http://localhost:8000/api/projects/${projectId}/lines/update`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    line_no: line.line_no,
                    new_text: newText,
                    nusha_index: nushaIndex
                })
            });
            if (!res.ok) throw new Error("Save failed");
            updateLineText(line.line_no, newText);
            setIsEdited(true);
        } catch (err) {
            console.error("Auto-save error:", err);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div
            className={`
                rounded-lg p-3 my-1.5 transition-all cursor-pointer relative group
                ${isActive
                    ? "bg-slate-800 border border-amber-500/50 ring-1 ring-amber-500/20 shadow-lg shadow-amber-500/5"
                    : "bg-slate-800/50 border border-slate-700/50 hover:border-slate-600 hover:bg-slate-800"
                }
            `}
            onClick={onSelect}
            data-line={line.line_no}
        >
            {/* Line number + status row */}
            <div className="flex items-center gap-2 mb-1.5">
                <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-bold text-slate-500 bg-slate-700/50 px-1.5 py-0.5 rounded tabular-nums min-w-[1.5rem] text-center">
                        {line.line_no}
                    </span>
                    {statusIcon}
                </div>

                {/* Saving indicator */}
                {isSaving && (
                    <div className="flex items-center gap-1 bg-blue-500/10 px-2 py-0.5 rounded text-[10px] text-blue-400 font-medium animate-pulse ml-auto">
                        <Save size={9} /> Kaydediliyor...
                    </div>
                )}

                {/* Delete button — visible on hover */}
                <button
                    onClick={async (e) => {
                        e.stopPropagation();
                        if (isDeleting) return;
                        if (!window.confirm(`Satır ${line.line_no} silinecek. Emin misiniz?`)) return;
                        setIsDeleting(true);
                        await deleteLine(line.line_no);
                        setIsDeleting(false);
                    }}
                    disabled={isDeleting}
                    className="p-1 text-slate-600 hover:text-red-400 hover:bg-red-500/10 rounded opacity-0 group-hover:opacity-100 transition-all ml-auto disabled:opacity-50"
                    title="Satırı Sil"
                >
                    <Trash2 size={12} />
                </button>
            </div>

            {/* Editable Content */}
            <pre
                ref={contentRef}
                className="whitespace-pre-wrap leading-loose outline-none text-slate-100"
                style={{
                    fontSize: `${fontSize}px`,
                    direction: "rtl",
                    fontFamily: '"Traditional Arabic", "Noto Naskh Arabic", serif'
                }}
                contentEditable
                suppressContentEditableWarning
                dangerouslySetInnerHTML={{ __html: htmlContent }}
                onClick={(e) => {
                    e.stopPropagation();
                    const target = e.target as HTMLElement;
                    if (target.tagName === "SPAN" && target.hasAttribute("data-meta")) {
                        try {
                            const metaStr = target.getAttribute("data-meta");
                            if (metaStr) {
                                const meta = JSON.parse(metaStr);
                                setErrorPopupData(meta);
                            }
                        } catch (err) {
                            console.error("Failed to parse error meta", err);
                        }
                    }
                }}
                onBlur={() => {
                    if (contentRef.current) {
                        saveText(contentRef.current.innerText);
                    }
                }}
            />

            {/* OCR Text Display */}
            {line.ocr_text && (
                <div className="mt-2 pt-2 border-t border-slate-700/50">
                    <div className="text-[10px] text-slate-500 font-bold mb-1 flex gap-1 items-center">
                        <span>🔍 OCR</span>
                    </div>
                    <div
                        className="text-sm text-slate-500 leading-loose bg-slate-900/50 p-2 rounded select-none pointer-events-none"
                        style={{
                            direction: "rtl",
                            fontFamily: '"Traditional Arabic", "Noto Naskh Arabic", serif'
                        }}
                    >
                        {line.ocr_text}
                    </div>
                </div>
            )}

            {/* Line Image */}
            {line.image_url && (
                <div className="mt-2 pt-2 border-t border-slate-700/50 flex flex-col items-center">
                    <span className="text-[10px] text-slate-500 font-bold mb-1 w-full text-left">🖼️ Satır</span>
                    <img
                        src={line.image_url}
                        alt={`Line ${line.line_no}`}
                        className="max-h-14 border border-slate-700 rounded object-contain bg-slate-950"
                    />
                </div>
            )}

            {/* AI Suggestions */}
            {line.line_marks && line.line_marks.length > 0 && (
                <div className="mt-2 text-sm border-t border-slate-700/50 pt-2 bg-slate-900/50 rounded p-2">
                    {line.line_marks.map((mark: any, idx: number) => {
                        if (mark.type === "ai_suggestion" || mark.suggestion) {
                            return (
                                <div key={idx} className="mb-1 flex flex-col gap-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-xs bg-blue-500/20 text-blue-400 px-1.5 rounded">
                                            {mark.source || "AI"}
                                        </span>
                                        <span className="text-slate-300 font-medium text-xs" dir="rtl">
                                            {mark.suggestion}
                                        </span>
                                    </div>
                                    {mark.reason && (
                                        <div className="text-xs text-slate-500 italic">
                                            {mark.reason}
                                        </div>
                                    )}
                                </div>
                            );
                        }
                        return null;
                    })}
                </div>
            )}
        </div>
    );
}
