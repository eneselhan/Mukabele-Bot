"use client";

import React, { useState, useMemo } from "react";
import { useMukabele } from "./MukabeleContext";
import { ChevronLeft, ChevronRight, AlertCircle } from "lucide-react";

export default function FloatingNav() {
    const { lines, setActiveLine } = useMukabele();
    const [navState, setNavState] = useState<{ [key: string]: number }>({});
    const [lastMsg, setLastMsg] = useState("");

    // Identify all errors
    // Group by source: gemini, openai, claude, gptgem (both), gptclaude (both), all3
    const errorGroups = useMemo(() => {
        const groups: { [key: string]: number[] } = {
            gemini: [],
            openai: [], // GPT
            claude: [],
            gptgem: [],
            gptclaude: [],
            all3: []
        };

        lines.forEach(line => {
            const marks = line.line_marks || [];
            if (!marks.length) return;

            // We only care if line has AT LEAST one error of that type.
            // Or do we iterate over every single error span?
            // Legacy viewer: `_allErrMarksGlobal()` flattens all marks across all lines.
            // For simplicity, let's jump to the LINE containing the error.
            // If a line has multiple errors of same type, we land on the line once.

            const sources = new Set<string>();
            marks.forEach((m: any) => {
                (m.sources || []).forEach((s: string) => sources.add(s));
            });

            if (sources.has("gemini")) groups.gemini.push(line.line_no);
            if (sources.has("openai")) groups.openai.push(line.line_no);
            if (sources.has("claude")) groups.claude.push(line.line_no);

            if (sources.has("gemini") && sources.has("openai")) groups.gptgem.push(line.line_no);
            if (sources.has("openai") && sources.has("claude")) groups.gptclaude.push(line.line_no);
            if (sources.has("gemini") && sources.has("openai") && sources.has("claude")) groups.all3.push(line.line_no);
        });

        // Deduplicate? No, pushing line_no multiple times if multiple marks?
        // Let's just store line_nos. If line 5 has 3 gemini errors, legacy behavior was iterating over marks (gidx).
        // Implementing gidx-level navigation is complex because we don't store flattened marks easily here.
        // Let's stick to Line-level navigation for V1.
        return groups;

    }, [lines]);

    const jumpTo = (key: string, label: string) => {
        const list = errorGroups[key];
        if (!list || !list.length) {
            setLastMsg(`${label}: 0`);
            setTimeout(() => setLastMsg(""), 2000);
            return;
        }

        let idx = navState[key] ?? -1;
        idx = (idx + 1) % list.length;

        setNavState(prev => ({ ...prev, [key]: idx }));
        setActiveLine(list[idx]);
        setLastMsg(`${label}: ${idx + 1}/${list.length}`);
        setTimeout(() => setLastMsg(""), 2000);
    };

    return (
        <div className="fixed left-4 top-32 z-30 bg-white/90 backdrop-blur-sm border border-slate-200 shadow-lg rounded-xl p-3 flex flex-col gap-2 w-48 transition-opacity hover:opacity-100 opacity-60">
            <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase cursor-grab active:cursor-grabbing border-b border-slate-100 pb-1 mb-1">
                <span className="flex items-center gap-1"><AlertCircle size={12} /> AI Hata Nav</span>
            </div>

            <div className="flex flex-col gap-1.5">
                <NavBtn label="Gemini" onClick={() => jumpTo("gemini", "Gemini")} count={errorGroups.gemini.length} />
                <NavBtn label="GPT" onClick={() => jumpTo("openai", "GPT")} count={errorGroups.openai.length} />
                <NavBtn label="Claude" onClick={() => jumpTo("claude", "Claude")} count={errorGroups.claude.length} />
                <div className="h-px bg-slate-100 my-0.5" />
                <NavBtn label="GPT+Gemini" onClick={() => jumpTo("gptgem", "GPT+Gem")} count={errorGroups.gptgem.length} />
                <NavBtn label="GPT+Claude" onClick={() => jumpTo("gptclaude", "GPT+Cld")} count={errorGroups.gptclaude.length} />
                <NavBtn label="3'ü Ortak" onClick={() => jumpTo("all3", "3'ü Ortak")} count={errorGroups.all3.length} />
            </div>

            {lastMsg && (
                <div className="absolute top-full left-0 mt-2 w-full text-center bg-black/70 text-white text-xs py-1 rounded">
                    {lastMsg}
                </div>
            )}
        </div>
    );
}

function NavBtn({ label, onClick, count }: { label: string, onClick: () => void, count: number }) {
    return (
        <button
            onClick={onClick}
            disabled={count === 0}
            className="flex items-center justify-between px-2 py-1.5 text-xs bg-slate-50 border border-slate-100 rounded hover:bg-white hover:shadow-sm disabled:opacity-40 transition-all text-left"
        >
            <span className="font-medium text-slate-700">{label}</span>
            <span className="bg-slate-200 text-slate-600 px-1.5 rounded-full text-[10px] min-w-[1.2rem] text-center">{count}</span>
        </button>
    );
}
