"use client";

import React, { useEffect, useRef } from "react";
import { useMukabele } from "./MukabeleContext";
import LineItem from "./LineItem";
import TextPanelToolbar from "./TextPanelToolbar";
import TextPanelFooter from "./TextPanelFooter";

export default function LineList() {
    const {
        activeLine,
        setActiveLine,
        fontSize,
        pages,
        activePageKey
    } = useMukabele();

    const listRef = useRef<HTMLDivElement>(null);

    const displayLines = React.useMemo(() => {
        if (!activePageKey) return [];
        const page = pages.find(p => p.key === activePageKey);
        return page ? page.lines : [];
    }, [pages, activePageKey]);

    // Scroll active line into view
    useEffect(() => {
        if (activeLine === null || !listRef.current) return;
        const el = listRef.current.querySelector(`[data-line="${activeLine}"]`);
        if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }, [activeLine]);

    return (
        <div className="flex flex-col h-full bg-slate-900 relative">
            <TextPanelToolbar />

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
                        />
                    );
                })}
            </div>

            <TextPanelFooter />
        </div>
    );
}
