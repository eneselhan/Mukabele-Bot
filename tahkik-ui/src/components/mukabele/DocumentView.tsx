"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import { useMukabele, Footnote } from "./MukabeleContext";
import { useParams } from "next/navigation";
import { AlertCircle, Plus, Minus, Type, X, Check } from "lucide-react";
import { v4 as uuidv4 } from "uuid";

export default function DocumentView() {
    const {
        pages,
        activePageKey,
        activeLine,
        setActiveLine,
        updateLineText,
        fontSize,
        footnotes,
        addFootnote,
        deleteFootnote,
        siglas,
        mergeLines,
        splitLine,
        nushaIndex,
        updateFootnote,
        baseNushaIndex
    } = useMukabele();

    const params = useParams();
    const projectId = params.projectId as string;

    const containerRef = useRef<HTMLDivElement>(null);
    const [selectedLines, setSelectedLines] = useState<number[]>([]);
    const [selection, setSelection] = useState<{
        text: string;
        lineNo: number;
        index: number;
        endIndex?: number;
        range?: Range;
        rect?: DOMRect;
    } | null>(null);

    const [menuOpen, setMenuOpen] = useState(false);
    const [menuType, setMenuType] = useState<"variation" | "omission" | "addition" | null>(null);
    const [menuInput, setMenuInput] = useState("");
    const [targetNusha, setTargetNusha] = useState(2); // Default to B (2)
    const [editingFootnote, setEditingFootnote] = useState<Footnote | null>(null);

    // ... (existing code)

    const handleUpdateFootnote = async () => {
        if (!editingFootnote) return;

        // Auto delete if empty
        if (!menuInput.trim()) {
            if (confirm("Dipnot içeriği boş olduğu için silinecek. Onaylıyor musunuz?")) {
                await handleDeleteFootnote();
            }
            return;
        }

        await updateFootnote(editingFootnote.id, menuInput);
        setEditingFootnote(null);
        setMenuInput("");
        setMenuOpen(false);
    };

    const handleDeleteFootnote = async () => {
        if (!editingFootnote) return;
        // if (confirm("Dipnotu silmek istediğinize emin misiniz?")) { // Removed confirm for explicit delete button? Or kept?
        // User asked for "empty content deletes it". 
        // Existing delete button logic:
        if (confirm("Dipnotu silmek istediğinize emin misiniz?")) {
            await deleteFootnote(editingFootnote.id);
            setEditingFootnote(null);
            setMenuInput("");
            setMenuOpen(false);
        }
    };

    // Scroll active line into view
    useEffect(() => {
        if (activeLine === null || !containerRef.current) return;
        // Find line span by data-line-no
        // Note: The spans are inside the container's dangerouslySetInnerHTML if using that, 
        // OR as mapped elements. In DocumentView they are mapped elements.
        const el = containerRef.current.querySelector(`[data-line-no="${activeLine}"]`);
        if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }, [activeLine]);

    // Handle Selection (Variation / Omission)
    useEffect(() => {
        const handleSelection = () => {
            const sel = window.getSelection();
            if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
                if (!menuOpen) setSelection(null);
                return;
            }

            const range = sel.getRangeAt(0);

            // Find the line container
            let container = range.commonAncestorContainer as HTMLElement;
            if (container.nodeType === Node.TEXT_NODE) {
                container = container.parentElement as HTMLElement;
            }

            // Traverse up to find the line span
            while (container && !container.hasAttribute("data-line-no")) {
                container = container.parentElement as HTMLElement;
                if (!container || container === document.body) return; // Not in a line
            }

            if (container && container.hasAttribute("data-line-no")) {
                const lineNo = parseInt(container.getAttribute("data-line-no") || "0");
                let text = sel.toString();
                const rect = range.getBoundingClientRect();

                // Helper to calculate absolute index
                const calculateAbsoluteIndex = (root: HTMLElement, node: Node, offset: number) => {
                    let index = 0;
                    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
                    let currentNode = walker.nextNode();
                    while (currentNode) {
                        if (currentNode === node) {
                            return index + offset;
                        }
                        const parent = currentNode.parentElement;
                        if (parent && parent.getAttribute("data-ignore") === "true") {
                            // Skip markers
                        } else {
                            index += (currentNode.textContent || "").length;
                        }
                        currentNode = walker.nextNode();
                    }
                    return index;
                };

                const startIdx = calculateAbsoluteIndex(container, range.startContainer, range.startOffset);
                let endIdx = calculateAbsoluteIndex(container, range.endContainer, range.endOffset);

                // --- TRIM SELECTION (Visual Fix for trailing spaces) ---
                // If text ends with spaces, update the DOM selection to exclude them.
                // This updates the UI highlight and triggers a new selectionchange event.
                const trimmedText = text.trimEnd();
                const diff = text.length - trimmedText.length;
                if (diff > 0) {
                    try {
                        // Only attempt visual trim if ending in a text node
                        if (range.endContainer.nodeType === Node.TEXT_NODE) {
                            const newRange = range.cloneRange();
                            if (range.endOffset >= diff) {
                                newRange.setEnd(range.endContainer, range.endOffset - diff);
                                sel.removeAllRanges();
                                sel.addRange(newRange);
                                return; // Stop here, let the new event handle it
                            }
                        }
                    } catch (e) {
                        console.warn("Visual trim failed", e);
                    }

                    // Fallback: Just logical trim if visual fail
                    text = trimmedText;
                    endIdx -= diff;
                }
                // ------------------------------------------------

                // Multi-line check (fallback to roughly line detection if container differs)
                if (sel.rangeCount > 0 && !sel.isCollapsed) {
                    const startNode = sel.anchorNode?.parentElement;
                    const endNode = sel.focusNode?.parentElement;
                    // Simple check for multi-line based on data-line-no attributes if they differ
                    // But we already found a common ancestor 'container'. 
                    // If common ancestor is the line span, it's single line.
                    // If common ancestor is higher up (like the page div), it *might* be multi-line.

                    // Re-check start/end nodes for different lines
                    let sNode = sel.anchorNode?.parentElement as HTMLElement;
                    let eNode = sel.focusNode?.parentElement as HTMLElement;
                    while (sNode && !sNode.hasAttribute("data-line-no")) sNode = sNode.parentElement as HTMLElement;
                    while (eNode && !eNode.hasAttribute("data-line-no")) eNode = eNode.parentElement as HTMLElement;

                    if (sNode && eNode && sNode !== eNode) {
                        const startLine = parseInt(sNode.getAttribute("data-line-no") || "0");
                        const endLine = parseInt(eNode.getAttribute("data-line-no") || "0");

                        if (startLine !== endLine) {
                            const linesToMerge = [];
                            const min = Math.min(startLine, endLine);
                            const max = Math.max(startLine, endLine);
                            for (let i = min; i <= max; i++) linesToMerge.push(i);
                            setSelectedLines(linesToMerge);
                            setSelection({
                                text: sel.toString(),
                                lineNo: min,
                                index: 0,
                                endIndex: 0,
                                range: range.cloneRange(),
                                rect: rect
                            });
                            return;
                        }
                    }
                }

                // Single line selection
                setSelectedLines([]);
                setSelection({
                    text,
                    lineNo,
                    index: startIdx,
                    endIndex: endIdx, // Store end index for word-end footnotes
                    range: range.cloneRange(),
                    rect
                });

                // Sync: Update active line immediately on selection so image view scrolls to it
                if (activeLine !== lineNo) {
                    setActiveLine(lineNo);
                }
            } else {
                setSelection(null);
                setSelectedLines([]);
            }
        };

        document.addEventListener("selectionchange", handleSelection);
        return () => document.removeEventListener("selectionchange", handleSelection);
    }, [menuOpen]);

    // Footnote Actions
    const handleAddFootnote = async (type: "variation" | "omission" | "addition") => {
        if (!selection && type !== "addition") return;
        if (selectedLines.length > 1) return;

        // Auto-save Omission
        if (type === "omission") {
            // For omission, we save the selected text as the content
            await saveFootnote("omission", selection?.text || "");
            setSelection(null);
            window.getSelection()?.removeAllRanges();
            return;
        }

        // For Variation & Addition -> Open Menu
        setMenuType(type);
        setMenuOpen(true);
        setMenuInput(""); // Reset input

        // Set default target nusha to first available non-base
        if (baseNushaIndex === targetNusha) {
            const next = [1, 2, 3, 4].find(n => n !== baseNushaIndex);
            if (next) setTargetNusha(next);
        }
    };

    const saveFootnote = async (type: "variation" | "omission" | "addition", content: string) => {
        if (!selection && type !== "addition") return;

        const lineNo = selection?.lineNo || activeLine || 0;

        // Use endIndex for the footnote position so it appears at the end of the word
        // Default to index if endIndex is missing (backwards compatibility)
        const idx = selection?.endIndex ?? (selection?.index || 0);

        const footnote: Footnote = {
            id: uuidv4(),
            line_no: lineNo,
            index: idx,
            type: type,
            nusha_index: targetNusha,
            content: content
        };

        await addFootnote(footnote);
    };

    // Line Shifting
    const handleShiftLine = async (direction: "prev" | "next") => {
        if (!selection || !activePageKey) return;

        // Use minOffset for logic
        const splitIndex = selection.minOffset;
        const lineNo = selection.lineNo;

        try {
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/lines/shift`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    line_no: lineNo,
                    direction,
                    split_index: splitIndex,
                    nusha_index: nushaIndex
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Shift failed");
            }

            // Reload
            const pagesRes = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/pages?nusha=${nushaIndex}`);
            if (pagesRes.ok) {
                const pagesData = await pagesRes.json();
                setPages(pagesData);
            }
            setSelection(null);

        } catch (err) {
            console.error(err);
            alert("Satır kaydırma başarısız oldu.");
        }
    };



    // Render Menu (Floating Bubble)
    const renderMenu = () => {
        // If editing an existing footnote (Simple Bubble)
        if (editingFootnote) {
            // Find rect for this footnote
            const el = document.getElementById(`fn-${editingFootnote.id}`);
            if (!el) return null;
            const rect = el.getBoundingClientRect();

            return (
                <div
                    className="fixed z-50 bg-white shadow-xl rounded-lg border border-slate-200 p-2 flex flex-col gap-2 w-48 animate-in fade-in zoom-in duration-200"
                    style={{
                        top: rect.bottom + 5,
                        left: rect.left - 20
                    }}
                >
                    <div className="flex items-center justify-between text-xs font-bold text-slate-500 border-b pb-1">
                        <span>Düzenle</span>
                        <button onClick={() => setEditingFootnote(null)}><X size={14} /></button>
                    </div>

                    <input
                        autoFocus
                        className="w-full border border-slate-300 rounded px-2 py-1 text-sm font-arabic dir-rtl"
                        value={menuInput}
                        onChange={e => setMenuInput(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === "Enter") {
                                handleUpdateFootnote();
                            }
                        }}
                    />

                    <div className="flex gap-2">
                        <button
                            onClick={handleDeleteFootnote}
                            className="flex-1 bg-red-100 hover:bg-red-200 text-red-700 text-xs font-bold py-1.5 rounded"
                        >
                            Sil
                        </button>
                        <button
                            onClick={handleUpdateFootnote}
                            className="flex-1 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold py-1.5 rounded"
                        >
                            Kaydet
                        </button>
                    </div>
                </div>
            );
        }

        if (!selection) return null;

        // If bubble is open (Footnote Entry)
        if (menuOpen && menuType !== "omission") {
            return (
                <div
                    className="fixed z-50 bg-white shadow-xl rounded-lg border border-slate-200 p-3 flex flex-col gap-2 w-64 animate-in fade-in zoom-in duration-200"
                    style={{
                        top: selection.rect.bottom + 10,
                        left: selection.rect.left
                    }}
                >
                    <div className="flex items-center justify-between text-xs font-bold text-slate-500 border-b pb-1 mb-1">
                        <span>{menuType === "variation" ? "Fark Kaydı" : "Ziyade Kaydı"}</span>
                        <button onClick={() => setMenuOpen(false)}><X size={14} /></button>
                    </div>

                    {/* Nusha Selector */}
                    <div className="flex gap-1 justify-center py-1">
                        {[1, 2, 3, 4].map(n => {
                            if (n === baseNushaIndex) return null; // Hide Base Nusha
                            return (
                                <button
                                    key={n}
                                    onClick={() => setTargetNusha(n)}
                                    className={`w-6 h-6 rounded-full text-xs font-bold border ${targetNusha === n ? "bg-purple-600 text-white border-purple-600" : "bg-slate-50 text-slate-500 border-slate-200"}`}
                                >
                                    {siglas[n] || (n === 1 ? "A" : n === 2 ? "B" : n === 3 ? "C" : "D")}
                                </button>
                            );
                        })}
                    </div>

                    <input
                        autoFocus
                        className="w-full border border-slate-300 rounded px-2 py-1 text-sm font-arabic dir-rtl"
                        placeholder={menuType === "variation" ? "Farklı kelimeyi yazın..." : "Eklenen kelimeyi yazın..."}
                        value={menuInput}
                        onChange={e => setMenuInput(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === "Enter") {
                                saveFootnote(menuType!, menuInput);
                                setMenuOpen(false);
                                setSelection(null);
                                window.getSelection()?.removeAllRanges();
                            }
                        }}
                    />

                    <button
                        onClick={() => {
                            saveFootnote(menuType!, menuInput);
                            setMenuOpen(false);
                            setMenuInput("");
                            setSelection(null);
                            window.getSelection()?.removeAllRanges();
                        }}
                        className="bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold py-1.5 rounded"
                    >
                        Kaydet
                    </button>
                </div>
            );
        }

        // Multi-line selection -> Merge Menu
        if (selectedLines.length > 1) {
            return (
                <div
                    className="fixed z-50 bg-slate-800 text-white shadow-xl rounded-lg flex items-center p-1 gap-1 -translate-x-1/2 animate-in fade-in zoom-in duration-150"
                    style={{
                        top: selection.rect.top - 40,
                        left: selection.rect.left + (selection.rect.width / 2)
                    }}
                >
                    <button
                        onClick={async () => {
                            await mergeLines(nushaIndex, selectedLines);
                            setSelectedLines([]);
                            setSelection(null);
                            window.getSelection()?.removeAllRanges();
                        }}
                        className="flex items-center gap-1.5 px-2 py-1.5 hover:bg-slate-700 rounded transition-colors"
                    >
                        <span className="text-xs font-bold">Satırları Birleştir ({selectedLines.length})</span>
                    </button>
                </div>
            );
        }

        // Standard Menu (Fark, Noksan, Ziyade, Böl)
        return (
            <div
                className="fixed z-50 bg-slate-800 text-white shadow-xl rounded-lg flex items-center p-1 gap-1 -translate-x-1/2 animate-in fade-in zoom-in duration-150"
                style={{
                    top: selection.rect.top - 40,
                    left: selection.rect.left + (selection.rect.width / 2)
                }}
            >
                <button
                    onClick={() => handleAddFootnote("variation")}
                    className="flex items-center gap-1.5 px-2 py-1.5 hover:bg-slate-700 rounded transition-colors"
                >
                    <span className="font-bold text-amber-400">(:)</span>
                    <span className="text-xs font-bold">Fark</span>
                </button>
                <div className="w-[1px] h-4 bg-slate-600" />
                <button
                    onClick={() => handleAddFootnote("omission")}
                    className="flex items-center gap-1.5 px-2 py-1.5 hover:bg-slate-700 rounded transition-colors"
                >
                    <span className="font-bold text-red-400">(-)</span>
                    <span className="text-xs font-bold">Noksan</span>
                </button>
                <div className="w-[1px] h-4 bg-slate-600" />
                <button
                    onClick={() => handleAddFootnote("addition")}
                    className="flex items-center gap-1.5 px-2 py-1.5 hover:bg-slate-700 rounded transition-colors"
                >
                    <span className="font-bold text-green-400">(+)</span>
                    <span className="text-xs font-bold">Ziyade</span>
                </button>

                {/* Split Option (Only if single line selected and not empty) */}
                {selection.text.trim().length > 0 && (
                    <>
                        <div className="w-[1px] h-4 bg-slate-600" />
                        <button
                            onClick={async () => {
                                // Use accurate index if available, fall back to 0
                                const splitIdx = selection.index || 0;
                                if (confirm("Satırı bu noktadan bölmek istiyor musunuz?")) {
                                    await splitLine(nushaIndex, selection.lineNo, splitIdx);
                                    setSelection(null);
                                    window.getSelection()?.removeAllRanges();
                                }
                            }}
                            className="flex items-center gap-1.5 px-2 py-1.5 hover:bg-slate-700 rounded transition-colors"
                            title="Satırı buradan böl"
                        >
                            <span className="text-xs font-bold">Böl</span>
                        </button>
                    </>
                )}
            </div>
        );
    };

    const displayLines = React.useMemo(() => {
        return pages.flatMap(p => p.lines);
    }, [pages]);

    return (
        <div className="flex-1 bg-white overflow-y-auto p-4 md:p-8 flex justify-center relative">
            {selection && !menuOpen && renderMenu()}
            {menuOpen && renderMenu()}


            <div
                ref={containerRef}
                className="bg-white min-h-[50vh] w-full max-w-[210mm] p-[20mm] text-slate-900 border border-slate-100 shadow-sm"
                dir="rtl"
                style={{
                    direction: "rtl",
                    fontFamily: "'Amiri', 'Traditional Arabic', serif",
                    fontSize: `${fontSize}px`,
                    lineHeight: 2.0,
                    textAlign: "justify",
                    textAlignLast: "right"
                }}
            >
                {!displayLines.length && (
                    <div className="text-slate-400 text-center italic text-sm mt-10 select-none">
                        Metin yükleniyor veya bulunamadı.
                    </div>
                )}

                {displayLines.map((line) => {
                    const isActive = activeLine === line.line_no;
                    const lineFootnotes = footnotes.filter(f => f.line_no === line.line_no);

                    // Render line content with interleaved footnotes
                    const renderLineContent = () => {
                        const rawText = line.best?.raw || "";
                        if (lineFootnotes.length === 0) return rawText;

                        // Sort footnotes by index
                        const sorted = [...lineFootnotes].sort((a, b) => a.index - b.index);
                        const segments = [];
                        let cursor = 0;

                        sorted.forEach((fn, idx) => {
                            // Clamp index to text length
                            // Note: We might have multiple footnotes at same index
                            const safeIndex = Math.min(Math.max(0, fn.index), rawText.length);

                            // Text segment before marker
                            if (safeIndex > cursor) {
                                segments.push(
                                    <span key={`text-${cursor}`}>{rawText.slice(cursor, safeIndex)}</span>
                                );
                            }

                            // Marker
                            segments.push(
                                <span
                                    key={fn.id}
                                    id={`fn-${fn.id}`}
                                    className="footnote-marker select-none text-[0.6em] align-top text-purple-600 font-bold ml-0.5 cursor-pointer hover:bg-purple-100 rounded px-0.5"
                                    title={`${siglas[fn.nusha_index] || (fn.nusha_index === 1 ? "A" : fn.nusha_index === 2 ? "B" : fn.nusha_index === 3 ? "C" : "D")}${fn.type === "variation" ? ":" : fn.type === "omission" ? "-" : "+"} ${fn.content}`}
                                    contentEditable={false}
                                    data-ignore="true"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setEditingFootnote(fn);
                                        setMenuInput(fn.content); // Pre-fill
                                        setMenuOpen(false); // Close potential text menu
                                        setSelection(null); // Clear text selection
                                    }}
                                >
                                    {fn.type === "addition" ? `(+)` : `[${idx + 1}]`}
                                </span>
                            );

                            cursor = safeIndex;
                        });

                        // Remaining text
                        if (cursor < rawText.length) {
                            segments.push(
                                <span key={`text-${cursor}`}>{rawText.slice(cursor)}</span>
                            );
                        }

                        return segments;
                    };

                    return (
                        <React.Fragment key={line.line_no}>
                            <span
                                contentEditable
                                suppressContentEditableWarning
                                data-line-no={line.line_no}
                                className={`inline rounded px-0.5 transition-colors outline-none border-b-2 border-transparent hover:border-slate-200 relative caret-black ${isActive ? "bg-amber-50 border-amber-300" : ""
                                    }`}
                                onFocus={() => setActiveLine(line.line_no)}
                                onClick={() => setActiveLine(line.line_no)}
                                onBlur={(e) => {
                                    // 1. Detect Missing Footnotes (Native Deletion)
                                    // Check which footnote markers are STILL in the DOM
                                    const clone = e.currentTarget.cloneNode(true) as HTMLElement;
                                    const remainingMarkers = clone.querySelectorAll('.footnote-marker');
                                    const remainingIds = new Set<string>();
                                    remainingMarkers.forEach(m => {
                                        const id = m.id.replace('fn-', '');
                                        remainingIds.add(id);
                                        m.remove(); // Remove from clone to get clean text
                                    });

                                    // Compare with expected footnotes for this line
                                    lineFootnotes.forEach(fn => {
                                        if (!remainingIds.has(fn.id)) {
                                            // Footnote ID is missing -> User deleted it
                                            deleteFootnote(fn.id);
                                        }
                                    });

                                    // 2. Update Text
                                    const newText = clone.textContent || "";
                                    const oldText = line.best?.raw || "";
                                    if (newText !== oldText) {
                                        updateLineText(line.line_no, newText);
                                    }
                                }}
                            >
                                {renderLineContent()}
                            </span>
                            {/* Simple space for flow */}
                            <span className="select-none"> </span>
                        </React.Fragment>
                    );
                })}

                {/* Footnotes Section (Inside Page) */}
                {footnotes.length > 0 && (
                    <div className="mt-8 border-t border-slate-300 pt-4 pr-2 pb-12">
                        <div className="space-y-1.5">
                            {footnotes.sort((a, b) => a.line_no - b.line_no).map((fn, i) => {
                                const sigla = siglas[fn.nusha_index] || (fn.nusha_index === 1 ? "A" : "B"); // Default fallbacks
                                let content = "";
                                if (fn.type === "variation") content = ` : ${fn.content}`;
                                if (fn.type === "omission") content = ` - ${fn.content}`;
                                if (fn.type === "addition") content = ` + ${fn.content}`;

                                return (
                                    <div key={fn.id} className="text-sm flex items-start gap-1 group leading-normal">
                                        <span className="font-bold text-xs text-slate-500 min-w-[1.5rem] w-auto text-left select-none pt-1">
                                            {i + 1}
                                        </span>
                                        <span className="font-serif dir-rtl text-slate-800">
                                            <span className="font-bold text-amber-700">{sigla}</span>
                                            {content}
                                        </span>
                                        <button
                                            onClick={() => deleteFootnote(fn.id)}
                                            className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-500 transition-opacity mr-auto px-2"
                                            title="Sil"
                                        >
                                            <X size={12} />
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>

        </div>
    );
}
