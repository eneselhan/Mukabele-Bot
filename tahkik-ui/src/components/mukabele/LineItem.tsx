"use client";

import React, { useState, useRef, useEffect } from "react";
import { highlightTextArabic } from "./utils";
import { ChevronLeft, ChevronRight, Save, Check, AlertTriangle, Pencil, Trash2 } from "lucide-react";
import { LineData, useMukabele } from "./MukabeleContext";
import { useTTS } from "./TTSContext";
import { useParams } from "next/navigation";

interface LineItemProps {
    line: LineData;
    isActive: boolean;
    onSelect: () => void;
    fontSize: number;
    onShift?: (direction: "prev" | "next", splitIndex?: number) => void;
}

export default function LineItem({ line, isActive, onSelect, fontSize, onShift }: LineItemProps) {
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
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/lines/update`, {
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

    const handlePushNext = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!onShift || !contentRef.current) return;

        const text = contentRef.current.innerText || "";
        const lastSpace = text.lastIndexOf(" ");
        if (lastSpace === -1) return; // Can't move single word line? Or move whole?
        // Let's assume we need at least 1 word to stay? 
        // Or if simple logic: split at last space.
        // If "A B C", last space is after B. splitIndex = 3.
        // moving = text[3+1:] = "C".
        // remaining = text[:3] = "A B".
        // API expects split_index such that text[:idx] stays, text[idx:] moves.
        // So split_index = lastSpace + 1. (Include space in remaining? No, split logic handles strip/join).
        // My backend: moving = text[split_index:]. remaining = text[:split_index].

        // If I pass lastSpace + 1:
        // "A B C" -> "A B" and "C".
        // splitIndex = 4.
        // text[:4] = "A B ". text[4:] = "C".
        // Backend strips. Looks good.

        onShift("next", lastSpace + 1);
    };

    const handlePullPrev = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!onShift) return;
        onShift("prev"); // Parent calculates split for Prev line
    };

    return (
        <div
            className={`
                rounded-md p-1.5 my-0.5 transition-all cursor-pointer relative group border
                ${isActive
                    ? "bg-white border-amber-500 ring-1 ring-amber-500 shadow-sm z-10"
                    : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50 shadow-sm"
                }
            `}
            onClick={onSelect}
            data-line={line.line_no}
        >
            {/* Shift Buttons (Visible on Hover) - Smaller & Tighter */}
            <button
                onClick={handlePullPrev}
                className="absolute left-[-8px] top-1/2 -translate-y-1/2 p-0.5 bg-slate-100 hover:bg-slate-200 text-slate-600 border border-slate-300 rounded opacity-0 group-hover:opacity-100 transition-opacity z-20 shadow-sm"
                title="Önceki satırdan kelime çek"
            >
                <ChevronLeft size={12} />
            </button>
            <button
                onClick={handlePushNext}
                className="absolute right-[-8px] top-1/2 -translate-y-1/2 p-0.5 bg-slate-100 hover:bg-slate-200 text-slate-600 border border-slate-300 rounded opacity-0 group-hover:opacity-100 transition-opacity z-20 shadow-sm"
                title="Sonraki satıra kelime it"
            >
                <ChevronRight size={12} />
            </button>

            {/* Line Content Wrapper - Flex Row for Compactness */}
            <div className="flex gap-2 items-start">

                {/* Meta Column (Line No + Status) */}
                <div className="flex flex-col items-center gap-0.5 min-w-[1.2rem] shrink-0 pt-1">
                    <span className="text-[9px] font-bold text-slate-400 hover:text-slate-600 tabular-nums leading-none">
                        {line.line_no}
                    </span>
                    <div className="opacity-70">{statusIcon}</div>
                </div>

                {/* Main Content */}
                <div className="flex-1 min-w-0">
                    <pre
                        ref={contentRef}
                        className="whitespace-pre-wrap leading-relaxed outline-none text-slate-800"
                        style={{
                            fontSize: `${fontSize}px`,
                            direction: "rtl",
                            fontFamily: '"Traditional Arabic", "Noto Naskh Arabic", serif',
                            padding: "0 2px"
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

                    {/* Inline Actions Row (Only visible if needed or hover) */}
                    <div className="flex items-center justify-end gap-2 mt-0.5 h-3">
                        {isSaving && (
                            <div className="flex items-center gap-1 text-[9px] text-blue-400 font-medium animate-pulse">
                                <Save size={8} /> <span>Kayıt...</span>
                            </div>
                        )}
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
                            className="text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Satırı Sil"
                        >
                            <Trash2 size={10} />
                        </button>
                    </div>
                </div>
            </div>

            {/* AI Suggestions (Compact) */}
            {line.line_marks && line.line_marks.length > 0 && (
                <div className="mt-1 text-xs border-t border-slate-700/30 pt-1">
                    {line.line_marks.slice(0, 1).map((mark: any, idx: number) => { // Show only 1st suggestion to save space, maybe? Or compact list
                        if (mark.type === "ai_suggestion" || mark.suggestion) {
                            return (
                                <div key={idx} className="flex items-center gap-1.5 overflow-hidden text-[10px] text-slate-400">
                                    <span className="font-bold bg-blue-500/10 text-blue-400 px-1 rounded-[2px] leading-tight">
                                        {mark.source || "AI"}
                                    </span>
                                    <span className="truncate" dir="rtl">{mark.suggestion}</span>
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
