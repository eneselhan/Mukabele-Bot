"use client";

import React, { useEffect, useRef } from "react";
import { useMukabele } from "./MukabeleContext";
import LineItem from "./LineItem";
import DocumentView from "./DocumentView";
import EditorView from "./EditorView";

import { useParams } from "next/navigation";

export default function LineList() {
    const params = useParams();
    const projectId = params.id as string;
    const {
        activeLine,
        setActiveLine,
        fontSize,
        pages,
        activePageKey,
        viewMode,
        lines, // Global lines
        refreshData,
        nushaIndex,
        mergeLines // Context method
    } = useMukabele();

    const listRef = useRef<HTMLDivElement>(null);

    const displayLines = React.useMemo(() => {
        if (!activePageKey) return [];
        const page = pages.find(p => p.key === activePageKey);
        return page ? page.lines : [];
    }, [pages, activePageKey]);

    // Handle Shift (Move Words)
    const handleShift = async (lineNo: number, direction: "prev" | "next", splitIndex?: number) => {
        if (!projectId) return;

        // Find global index
        const globalIdx = lines.findIndex(l => l.line_no === lineNo);
        if (globalIdx === -1) return;

        let targetLineNo = lineNo;
        let apiDirection = direction;
        let finalSplitIndex = splitIndex ?? 0;

        // Logic Mapping
        if (direction === "prev") {
            // "Pull from Prev" -> Technically "Push from Prev to Next"
            // We want to move last word of PrevLine to CurrentLine.
            if (globalIdx === 0) return; // No prev line

            const prevLine = lines[globalIdx - 1];
            targetLineNo = prevLine.line_no;
            apiDirection = "next"; // We push FROM prev TO current

            // Calculate split index for last word of prev line
            const txt = prevLine.best?.raw || "";
            const lastSpace = txt.lastIndexOf(" ");
            // If -1, whole text moves? Yes. split=0.
            // If "A B", space at 1. split=2 ("B").
            finalSplitIndex = lastSpace + 1;
        }
        else if (direction === "next") {
            // "Push to Next" -> Pushing from Current to Next.
            // splitIndex is provided by LineItem (start of moving part).
            // Default apiDirection="next" is correct.
            targetLineNo = lineNo;
            apiDirection = "next";
        }

        try {
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/lines/shift`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    nusha_index: nushaIndex,
                    line_no: targetLineNo,
                    direction: apiDirection,
                    split_index: finalSplitIndex
                })
            });

            if (res.ok) {
                await refreshData();
            } else {
                const err = await res.json();
                alert(`Hata: ${err.detail || "İşlem başarısız"}`);
            }
        } catch (e) {
            console.error("Shift failed", e);
            alert("Sunucu hatası");
        }
    };

    // Scroll active line into view
    useEffect(() => {
        if (activeLine === null || !listRef.current) return;
        const el = listRef.current.querySelector(`[data-line="${activeLine}"]`);

        if (el) {
            const rect = el.getBoundingClientRect();
            const containerRect = listRef.current.getBoundingClientRect();
            const isVisible = (
                rect.top >= containerRect.top &&
                rect.bottom <= containerRect.bottom
            );

            if (!isVisible) {
                el.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
    }, [activeLine]);

    return (
        <div className="flex flex-col h-full bg-slate-50 relative">
            {viewMode === 'paper' ? (
                <DocumentView />
            ) : viewMode === 'editor' ? (
                <EditorView />
            ) : (
                <div
                    ref={listRef}
                    className="flex-1 overflow-y-auto px-3 py-2 scroll-smooth"
                >
                    {!displayLines.length && (
                        <div className="text-slate-500 text-center mt-10 text-sm">
                            {activePageKey ? "Bu sayfada metin yok." : "Sayfa seçili değil."}
                        </div>
                    )}

                    {displayLines.map((line, i) => {
                        const uniqueKey = line.line_no != null ? line.line_no : `idx-${i}`;
                        return (
                            <LineItem
                                key={uniqueKey}
                                line={line}
                                isActive={line.line_no === activeLine}
                                onSelect={() => line.line_no != null && setActiveLine(line.line_no)}
                                fontSize={fontSize}
                                onShift={(dir, split) => handleShift(line.line_no, dir, split)}
                            />
                        );
                    })}
                </div>
            )}
        </div>
    );
}
