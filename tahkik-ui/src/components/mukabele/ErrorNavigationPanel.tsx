"use client";

import React, { useState, useMemo } from "react";
import { useMukabele } from "./MukabeleContext";
import { X, GripVertical } from "lucide-react";

interface ErrorMark {
    line_no: number;
    gidx: number;
    sources: string[];
    wrong: string;
    suggestion: string;
    reason: string;
    paragraph_index?: number;
}

export default function ErrorNavigationPanel() {
    const { data, lines, setActiveLine } = useMukabele();
    const [position, setPosition] = useState({ x: 14, y: 108 });
    const [isDragging, setIsDragging] = useState(false);
    const [navState, setNavState] = useState<{ [key: string]: number }>({
        gemini: -1,
        openai: -1,
        claude: -1,
        gptgem: -1,
        gptclaude: -1,
        all3: -1
    });
    const [currentInfo, setCurrentInfo] = useState<string>("");

    // Extract all error marks from all lines
    const allErrorMarks = useMemo((): ErrorMark[] => {
        if (!data) return [];

        const marks: ErrorMark[] = [];
        const allAligned = [
            ...(data.aligned || []),
            ...(data.aligned_alt || []),
            ...(data.aligned_alt3 || []),
            ...(data.aligned_alt4 || [])
        ];

        for (const item of allAligned) {
            if (!item || typeof item !== "object") continue;
            const lineNo = item.line_no;
            const lineMarks = Array.isArray(item.line_marks) ? item.line_marks : [];

            for (const m of lineMarks) {
                if (!m || typeof m !== "object") continue;
                const gidx = m.gidx;
                if (typeof lineNo !== "number" || typeof gidx !== "number") continue;

                marks.push({
                    line_no: lineNo,
                    gidx,
                    sources: Array.isArray(m.sources) ? m.sources.map((s: any) => String(s || "").toLowerCase()) : [],
                    wrong: m.wrong || "",
                    suggestion: m.suggestion || "",
                    reason: m.reason || "",
                    paragraph_index: m.paragraph_index
                });
            }
        }

        // Sort by line_no, then gidx
        marks.sort((a, b) => (a.line_no - b.line_no) || (a.gidx - b.gidx));
        return marks;
    }, [data]);

    // Filter marks by source
    const getMarksBySource = (source: string): ErrorMark[] => {
        return allErrorMarks.filter(m => m.sources.includes(source.toLowerCase()));
    };

    const getMarksByGptGem = (): ErrorMark[] => {
        return allErrorMarks.filter(m =>
            m.sources.includes("gemini") && m.sources.includes("openai")
        );
    };

    const getMarksByGptClaude = (): ErrorMark[] => {
        return allErrorMarks.filter(m =>
            m.sources.includes("openai") && m.sources.includes("claude")
        );
    };

    const getMarksByAllThree = (): ErrorMark[] => {
        return allErrorMarks.filter(m =>
            m.sources.includes("gemini") &&
            m.sources.includes("openai") &&
            m.sources.includes("claude")
        );
    };

    // Navigate through errors
    const gotoMarkList = (key: string, marks: ErrorMark[], label: string) => {
        if (!marks || marks.length === 0) return;

        const cur = navState[key] ?? -1;
        const next = (cur + 1) % marks.length;

        setNavState(prev => ({ ...prev, [key]: next }));

        const mark = marks[next];
        setCurrentInfo(`${label}: ${next + 1}/${marks.length}`);

        // Jump to line
        if (mark) {
            setActiveLine(mark.line_no);

            // Auto-hide info after 2.2s
            setTimeout(() => setCurrentInfo(""), 2200);
        }
    };

    const handleDragStart = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsDragging(true);

        const startX = e.clientX - position.x;
        const startY = e.clientY - position.y;

        const handleMove = (moveE: MouseEvent) => {
            setPosition({
                x: moveE.clientX - startX,
                y: moveE.clientY - startY
            });
        };

        const handleUp = () => {
            setIsDragging(false);
            document.removeEventListener("mousemove", handleMove);
            document.removeEventListener("mouseup", handleUp);
        };

        document.addEventListener("mousemove", handleMove);
        document.addEventListener("mouseup", handleUp);
    };

    // Count errors per source
    const geminiCount = getMarksBySource("gemini").length;
    const gptCount = getMarksBySource("openai").length;
    const claudeCount = getMarksBySource("claude").length;
    const gptGemCount = getMarksByGptGem().length;
    const gptClaudeCount = getMarksByGptClaude().length;
    const all3Count = getMarksByAllThree().length;
    const totalErrors = allErrorMarks.length;

    if (totalErrors === 0) return null;

    return (
        <div
            className="fixed z-50 bg-white/95 backdrop-blur-sm border border-slate-300 rounded-2xl shadow-2xl p-2 min-w-[320px] max-w-[400px]"
            style={{
                left: `${position.x}px`,
                top: `${position.y}px`,
                cursor: isDragging ? "grabbing" : "default"
            }}
        >
            {/* Drag Handle */}
            <div
                className="flex items-center justify-center w-full py-1 cursor-grab active:cursor-grabbing bg-slate-100 rounded-lg mb-2"
                onMouseDown={handleDragStart}
            >
                <GripVertical size={16} className="text-slate-400" />
                <span className="text-xs font-bold text-slate-500 ml-1 tracking-wide">HATA NAVİGASYONU</span>
            </div>

            {/* Info Display */}
            {currentInfo && (
                <div className="text-xs text-center bg-blue-50 text-blue-700 rounded-lg py-1 px-2 mb-2 font-medium">
                    {currentInfo}
                </div>
            )}

            {/* Total Error Count */}
            <div className="text-sm text-center bg-red-50 text-red-700 rounded-lg py-1 px-2 mb-2 font-semibold">
                Toplam Hata: {totalErrors}
            </div>

            {/* Navigation Buttons */}
            <div className="flex flex-col gap-1.5">
                <button
                    onClick={() => gotoMarkList("gemini", getMarksBySource("gemini"), "Gemini")}
                    disabled={geminiCount === 0}
                    className="text-left text-sm px-3 py-2 bg-orange-100 hover:bg-orange-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium text-orange-900 transition-colors"
                >
                    🔶 Gemini ({geminiCount})
                </button>

                <button
                    onClick={() => gotoMarkList("openai", getMarksBySource("openai"), "GPT")}
                    disabled={gptCount === 0}
                    className="text-left text-sm px-3 py-2 bg-blue-100 hover:bg-blue-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium text-blue-900 transition-colors"
                >
                    🔷 GPT ({gptCount})
                </button>

                <button
                    onClick={() => gotoMarkList("claude", getMarksBySource("claude"), "Claude")}
                    disabled={claudeCount === 0}
                    className="text-left text-sm px-3 py-2 bg-purple-100 hover:bg-purple-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium text-purple-900 transition-colors"
                >
                    🟣 Claude ({claudeCount})
                </button>

                <div className="border-t border-slate-200 my-1"></div>

                <button
                    onClick={() => gotoMarkList("gptgem", getMarksByGptGem(), "GPT+Gemini ortak")}
                    disabled={gptGemCount === 0}
                    className="text-left text-sm px-3 py-2 bg-amber-100 hover:bg-amber-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium text-amber-900 transition-colors"
                >
                    🟠 GPT+Gemini ({gptGemCount})
                </button>

                <button
                    onClick={() => gotoMarkList("gptclaude", getMarksByGptClaude(), "GPT+Claude ortak")}
                    disabled={gptClaudeCount === 0}
                    className="text-left text-sm px-3 py-2 bg-indigo-100 hover:bg-indigo-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium text-indigo-900 transition-colors"
                >
                    🔵 GPT+Claude ({gptClaudeCount})
                </button>

                <button
                    onClick={() => gotoMarkList("all3", getMarksByAllThree(), "3'ü ortak")}
                    disabled={all3Count === 0}
                    className="text-left text-sm px-3 py-2 bg-green-100 hover:bg-green-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium text-green-900 transition-colors"
                >
                    ✅ 3'ü Ortak ({all3Count})
                </button>
            </div>
        </div>
    );
}
