"use client";

import React, { useState, useRef, useEffect } from "react";
import { highlightTextArabic } from "./utils";
import { Save } from "lucide-react";
import { LineData, useMukabele } from "./MukabeleContext";
import { useTTS } from "./TTSContext"; // Import useTTS
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
    const { setErrorPopupData, nushaIndex, updateLineText } = useMukabele();
    const { activeWordIndex } = useTTS(); // Get TTS state

    const [isSaving, setIsSaving] = useState(false);
    const contentRef = useRef<HTMLPreElement>(null);
    const [htmlContent, setHtmlContent] = useState("");

    // Initialize HTML content
    useEffect(() => {
        const raw = line.best?.raw || "";
        const start = line.best?.start_word || 0;
        const marks = line.line_marks || [];

        setHtmlContent(highlightTextArabic(raw, start, marks, activeWordIndex));
    }, [line, activeWordIndex]);

    // Auto-save logic
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

            // Update local state immediately so UI reflects the change
            updateLineText(line.line_no, newText);
        } catch (err) {
            console.error("Auto-save error:", err);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div
            className={`
                border rounded-lg p-3 my-2 transition-all cursor-pointer relative
                ${isActive ? "border-slate-800 ring-2 ring-slate-100 shadow-sm" : "border-slate-200 hover:border-slate-400"}
            `}
            onClick={onSelect}
            data-line={line.line_no}
        >
            {/* Status Indicator (Absolute Top Right) */}
            {isSaving && (
                <div className="absolute top-2 right-2 flex items-center gap-1 bg-blue-50 px-2 py-0.5 rounded text-[10px] text-blue-600 font-bold border border-blue-100 animate-pulse">
                    <Save size={10} /> Kaydediliyor...
                </div>
            )}

            {/* Editable Content */}
            <pre
                ref={contentRef}
                className="whitespace-pre-wrap font-serif leading-loose outline-none pt-2"
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
                    // Check if clicked on error span
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
                onBlur={(e) => {
                    if (contentRef.current) {
                        const currentText = contentRef.current.innerText;
                        // Basic check to avoid saving same content implies tracking initial?
                        // For now just save on blur to be safe.
                        saveText(currentText);
                    }
                }}
            />

            {/* OCR Text Display (Reference) */}
            {line.ocr_text && (
                <div className="mt-2 pt-2 border-t border-slate-100">
                    <div className="text-[10px] items-center text-slate-400 font-bold mb-1 flex gap-1">
                        <span>🔍 OCR Metni</span>
                    </div>
                    <div
                        className="text-sm text-slate-500 font-serif leading-loose bg-slate-50 p-2 rounded select-none pointer-events-none opacity-80"
                        style={{
                            direction: "rtl",
                            fontFamily: '"Traditional Arabic", "Noto Naskh Arabic", serif'
                        }}
                    >
                        {line.ocr_text}
                    </div>
                </div>
            )}

            {/* AI Suggestions / Metadata Display */}
            {line.line_marks && line.line_marks.length > 0 && (
                <div className="mt-2 text-sm text-slate-500 border-t pt-2 bg-slate-50 rounded p-2">
                    {line.line_marks.map((mark: any, idx: number) => {
                        if (mark.type === "ai_suggestion" || mark.suggestion) {
                            return (
                                <div key={idx} className="mb-1 flex flex-col gap-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-xs bg-blue-100 text-blue-700 px-1 rounded">
                                            {mark.source || "AI"}
                                        </span>
                                        <span className="text-slate-700 font-medium">
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
