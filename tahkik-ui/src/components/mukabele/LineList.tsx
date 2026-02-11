"use client";

import React, { useEffect, useRef } from "react";
import { useMukabele } from "./MukabeleContext";
import LineItem from "./LineItem";

import SearchBox from "./SearchBox";

export default function LineList() {
    const {
        lines,
        activeLine,
        setActiveLine,
        fontSize,
        pages,
        activePageKey
    } = useMukabele();

    const listRef = useRef<HTMLDivElement>(null);

    // Filter lines for active page
    const displayLines = React.useMemo(() => {
        if (!activePageKey) return [];
        const page = pages.find(p => p.key === activePageKey);
        return page ? page.lines : [];
    }, [pages, activePageKey]);

    // Scroll active line into view
    useEffect(() => {
        if (activeLine === null || !listRef.current) return;

        // Find the element
        const el = listRef.current.querySelector(`[data-line="${activeLine}"]`);
        if (el) {
            el.scrollIntoView({
                behavior: "smooth",
                block: "center"
            });
        }
    }, [activeLine]);

    return (
        <div className="flex flex-col h-full bg-white relative">
            <SearchBox />

            <div
                ref={listRef}
                className="flex-1 overflow-y-auto p-4"
            >
                {!displayLines.length && <div className="text-slate-400 text-center mt-10">
                    {activePageKey ? "Bu sayfada metin yok." : "Sayfa seçili değil."}
                </div>}

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
        </div>
    );
}
