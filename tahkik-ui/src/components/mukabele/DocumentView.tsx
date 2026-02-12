"use client";

import React, { useRef, useEffect } from "react";
import { useMukabele } from "./MukabeleContext";

export default function DocumentView() {
    const {
        pages,
        activePageKey,
        activeLine,
        setActiveLine,
        updateLineText,
        fontSize
    } = useMukabele();

    const displayLines = React.useMemo(() => {
        if (!activePageKey) return [];
        const page = pages.find(p => p.key === activePageKey);
        return page ? page.lines : [];
    }, [pages, activePageKey]);

    const containerRef = useRef<HTMLDivElement>(null);

    // Scroll active line into view logic might need to be different here or handled by the parent
    // For now, let's keep it simple.

    return (
        <div className="flex-1 bg-slate-200 overflow-y-auto p-4 md:p-8 flex justify-center">
            <div
                ref={containerRef}
                className="bg-white shadow-xl min-h-[297mm] w-full max-w-[210mm] p-[20mm] text-right"
                style={{
                    direction: "rtl",
                    fontFamily: "'Amiri', 'Traditional Arabic', serif",
                    fontSize: `${fontSize}px`,
                    lineHeight: 2.2,
                    textAlign: "justify"
                }}
            >
                {!displayLines.length && (
                    <div className="text-slate-400 text-center italic text-sm mt-10 select-none">
                        {activePageKey ? "Bu sayfada metin yok." : "Sayfa seçili değil."}
                    </div>
                )}

                {displayLines.map((line) => {
                    const isActive = activeLine === line.line_no;
                    return (
                        <React.Fragment key={line.line_no}>
                            <span
                                contentEditable
                                suppressContentEditableWarning
                                className={`inline-block rounded px-0.5 transition-colors outline-none border border-transparent hover:border-slate-200 ${isActive ? "bg-amber-50 ring-1 ring-amber-200" : ""
                                    }`}
                                style={{ minWidth: "20px" }}
                                onFocus={() => setActiveLine(line.line_no)}
                                onClick={() => setActiveLine(line.line_no)}
                                onBlur={(e) => {
                                    const newText = e.currentTarget.innerText;
                                    const oldText = line.best?.raw || "";
                                    if (newText !== oldText) {
                                        updateLineText(line.line_no, newText);
                                    }
                                }}
                            >
                                {line.best?.raw || ""}
                            </span>
                            {/* Non-selectable space to prevent word merging issues */}
                            <span className="select-none text-transparent text-[0px] w-1 inline-block"> </span>
                            <span className="mx-1"> </span>
                        </React.Fragment>
                    );
                })}
            </div>
        </div>
    );
}
