"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import { useMukabele, Footnote } from "./MukabeleContext";
import { useParams } from "next/navigation";
import { AlertCircle, Plus, Minus, Type, X, Check, ArrowUp, Trash2 } from "lucide-react";
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
        // splitLine, // Removed as per previous task
        nushaIndex,
        updateFootnote,
        baseNushaIndex,
        setPages,
        refreshData
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
    const [hoveredLine, setHoveredLine] = useState<number | null>(null);

    // Undo State
    const [pendingDeletes, setPendingDeletes] = useState<Set<string>>(new Set());
    const [lastDeleted, setLastDeleted] = useState<{ fn: Footnote, timeoutId: NodeJS.Timeout } | null>(null);
    const [countdown, setCountdown] = useState(5);

    // ... (existing code)

    const handleUpdateFootnote = async () => {
        if (!editingFootnote) return;

        // Auto delete if empty
        if (!menuInput.trim()) {
            // User requested easy removal, so empty content auto-removes without confirm
            await handleDeleteFootnote();
            return;
        }

        await updateFootnote(editingFootnote.id, menuInput);
        setEditingFootnote(null);
        setMenuInput("");
        setMenuOpen(false);
    };

    const handleDeleteFootnote = async () => {
        if (!editingFootnote) return;
        // Direct delete without confirmation for "easy removal"
        await deleteFootnote(editingFootnote.id);
        setEditingFootnote(null);
        setMenuInput("");
        setMenuOpen(false);
    };

    // Scroll active line into view
    useEffect(() => {
        if (activeLine === null || !containerRef.current) return;
        const el = containerRef.current.querySelector(`[data-line-no="${activeLine}"]`);
        if (el) {
            const rect = el.getBoundingClientRect();
            const containerRect = containerRef.current.getBoundingClientRect();

            // Check if element is visible within the container
            const isVisible = (
                rect.top >= containerRect.top &&
                rect.bottom <= containerRect.bottom
            );

            if (!isVisible) {
                el.scrollIntoView({ behavior: "smooth", block: "center" });
            }
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
        document.addEventListener("selectionchange", handleSelection);
        return () => document.removeEventListener("selectionchange", handleSelection);
    }, [menuOpen]);

    // Countdown Logic
    useEffect(() => {
        if (!lastDeleted) return;

        const interval = setInterval(() => {
            setCountdown(prev => {
                if (prev <= 1) {
                    clearInterval(interval);
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(interval);
    }, [lastDeleted]);

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

        // Use index for logic
        const splitIndex = selection.index;
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
        if (menuOpen && menuType !== "omission" && selection.rect) {
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

        if (selectedLines.length > 1 && selection.rect) {
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
        if (selection.rect) {
            // Disable menu on Base Nusha (1) if requested
            if (nushaIndex === 1) return null;

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


                </div >
            );
        }
        return null;
    };

    // A4 Pagination Logic
    const PAGE_HEIGHT = 1123; // ~297mm @ 96 DPI
    const VERTICAL_PADDING = 150; // ~40mm total (top+bottom)
    const CONTENT_HEIGHT = PAGE_HEIGHT - VERTICAL_PADDING;

    // Helper to estimate line height
    const getLineHeight = (fontSize: number) => fontSize * 2.0;
    const getFootnoteHeight = () => 24; // Approx height of a footnote line

    const paginatedPages = React.useMemo(() => {
        const allLines = pages.flatMap(p => p.lines);
        const resultPages: { lines: typeof allLines, footnotes: Footnote[] }[] = [];

        let currentLines: typeof allLines = [];
        let currentFootnotes: Footnote[] = [];
        let currentHeight = 0;

        const HORIZONTAL_PADDING = 150; // ~40mm total (left+right)
        const TEXT_WIDTH = 794 - HORIZONTAL_PADDING; // ~210mm width - padding
        // 0.28 caused overflow. 0.35 caused gaps. Trying 0.32 to find the sweet spot.
        const AVG_CHAR_WIDTH = fontSize * 0.32;
        const CHARS_PER_LINE = Math.floor(TEXT_WIDTH / AVG_CHAR_WIDTH);

        for (const line of allLines) {
            const rawText = line.best?.raw || "";
            // Estimate visual lines closest to paragraph flow
            const charCount = rawText.length + 1; // +1 for space
            const estimatedVisualLines = charCount / CHARS_PER_LINE;
            const addedHeight = estimatedVisualLines * getLineHeight(fontSize);

            // Find footnotes for this line
            const lineFns = footnotes.filter(f => f.line_no === line.line_no && !pendingDeletes.has(f.id));
            const fnsH = lineFns.length * getFootnoteHeight();

            // Check if adding this segment exceeds page height
            if (currentHeight + addedHeight + fnsH > CONTENT_HEIGHT && currentLines.length > 0) {
                // Push current page
                resultPages.push({ lines: currentLines, footnotes: currentFootnotes });
                // Reset for next page
                currentLines = [];
                currentFootnotes = [];
                currentHeight = 0;
            }

            // Add to current
            currentLines.push(line);
            currentFootnotes.push(...lineFns);
            currentHeight += addedHeight + fnsH;
        }

        // Push last page
        if (currentLines.length > 0) {
            resultPages.push({ lines: currentLines, footnotes: currentFootnotes });
        }

        return resultPages;
    }, [pages, footnotes, fontSize, pendingDeletes]);

    // Sequential Numbering Logic
    const footnoteNumbers = React.useMemo(() => {
        const sorted = [...footnotes].sort((a, b) => {
            if (a.line_no !== b.line_no) return a.line_no - b.line_no;
            return a.index - b.index;
        });

        const map = new Map<string, number>();
        sorted.forEach((fn, idx) => {
            map.set(fn.id, idx + 1);
        });
        return map;
    }, [footnotes]);

    // Zoom Logic
    const [scale, setScale] = useState(1);

    useEffect(() => {
        if (!containerRef.current) return;
        const ro = new ResizeObserver(entries => {
            for (const entry of entries) {
                const w = entry.contentRect.width;
                // Target width: 794px (A4 @ 96 DPI) + 64px padding (32px each side)
                // Calculate scale to fit width minus padding
                const targetScale = (w - 64) / 794;
                setScale(Math.max(0.1, Math.min(targetScale, 3.0))); // Clamp
            }
        });
        ro.observe(containerRef.current);
        return () => ro.disconnect();
    }, []);

    return (
        <div ref={containerRef} className="flex-1 bg-slate-100 overflow-y-auto overflow-x-hidden p-0 relative">
            <div className="flex flex-col items-center w-full min-h-full py-8 gap-8">
                {selection && !menuOpen && renderMenu()}
                {menuOpen && renderMenu()}

                {!paginatedPages.length && (
                    <div className="text-slate-400 text-center italic text-sm mt-10 select-none">
                        Metin yükleniyor veya bulunamadı.
                    </div>
                )}

                {paginatedPages.map((page, pageIndex) => (
                    <div
                        key={pageIndex}
                        style={{
                            width: 794 * scale,
                            height: 1123 * scale,
                            position: "relative"
                        }}
                        className="transition-all duration-75 ease-out shadow-md" // shadow on wrapper
                    >
                        <div
                            id={`page-${pageIndex}`}
                            className="bg-white text-slate-900 absolute top-0 left-0 origin-top-left flex flex-col p-[20mm]"
                            dir="rtl"
                            style={{
                                width: 794,
                                height: 1123,
                                transform: `scale(${scale})`,
                                fontFamily: "'Amiri', 'Traditional Arabic', serif",
                                fontSize: `${fontSize}px`,
                                lineHeight: 2.0,
                                textAlign: "justify",
                                textAlignLast: "right"
                            }}
                        >
                            {/* Page Content */}
                            <div className="flex-1">
                                {page.lines.map((line) => {
                                    const isActive = activeLine === line.line_no;
                                    const lineFootnotes = footnotes.filter(f => f.line_no === line.line_no);

                                    // Render line content with interleaved footnotes
                                    const renderLineContent = () => {
                                        const rawText = line.best?.raw || "";
                                        const isHovered = hoveredLine === line.line_no;
                                        const isBaseNusha = nushaIndex === baseNushaIndex; // Check if current view is Base

                                        // Sort footnotes by index
                                        const sorted = [...lineFootnotes].sort((a, b) => a.index - b.index);

                                        const segments: React.ReactNode[] = [];
                                        let cursor = 0;
                                        let segmentKeyIndex = 0;

                                        sorted.forEach((fn, idx) => {
                                            // Clamp index
                                            const safeIndex = Math.min(Math.max(0, fn.index), rawText.length);

                                            // Text segment before marker
                                            if (safeIndex > cursor) {
                                                segments.push(
                                                    <span key={`seg-${segmentKeyIndex++}`}>{rawText.slice(cursor, safeIndex)}</span>
                                                );
                                            }

                                            const fnNum = footnoteNumbers.get(fn.id) || 0;

                                            // Marker
                                            segments.push(
                                                <span
                                                    key={`fn-${fn.id}`}
                                                    id={`fn-${fn.id}`}
                                                    className="footnote-marker select-none text-[0.6em] align-top text-purple-600 font-bold ml-0.5 cursor-pointer hover:bg-purple-100 rounded px-0.5"
                                                    title={`${siglas[fn.nusha_index] || (fn.nusha_index === 1 ? "A" : fn.nusha_index === 2 ? "B" : fn.nusha_index === 3 ? "C" : "D")}${fn.type === "variation" ? ":" : fn.type === "omission" ? "-" : "+"} ${fn.content}`}
                                                    contentEditable={false}
                                                    data-ignore="true"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setEditingFootnote(fn);
                                                        setMenuInput(fn.content);
                                                        setMenuOpen(false);
                                                        setSelection(null);
                                                    }}
                                                >
                                                    {`[${fnNum}]`}
                                                </span>
                                            );

                                            cursor = safeIndex;
                                        });

                                        // Remaining text
                                        if (cursor < rawText.length) {
                                            segments.push(
                                                <span key={`seg-${segmentKeyIndex++}`}>{rawText.slice(cursor)}</span>
                                            );
                                        }

                                        // Default to rawText if empty segments
                                        if (segments.length === 0 && rawText.length > 0) {
                                            segments.push(<span key={`seg-${segmentKeyIndex++}`}>{rawText}</span>);
                                        }

                                        return (
                                            <React.Fragment key={line.line_no}>
                                                <span
                                                    data-line-no={line.line_no}
                                                    className={`inline rounded px-0.5 transition-colors outline-none border-b border-transparent hover:border-slate-200 caret-black ${isActive ? "bg-amber-50 border-amber-300" : ""}`}
                                                    contentEditable
                                                    suppressContentEditableWarning
                                                    onFocus={() => setActiveLine(line.line_no)}
                                                    onClick={() => setActiveLine(line.line_no)}
                                                    onBlur={(e) => {
                                                        const clone = e.currentTarget.cloneNode(true) as HTMLElement;
                                                        const remainingMarkers = clone.querySelectorAll('.footnote-marker');
                                                        const remainingIds = new Set<string>();
                                                        remainingMarkers.forEach(m => {
                                                            const id = m.id.replace('fn-', '');
                                                            remainingIds.add(id);
                                                            m.remove();
                                                        });
                                                        lineFootnotes.forEach(fn => {
                                                            if (!remainingIds.has(fn.id)) deleteFootnote(fn.id);
                                                        });
                                                        const newText = clone.textContent || "";
                                                        const oldText = line.best?.raw || "";
                                                        if (newText !== oldText) {
                                                            updateLineText(line.line_no, newText);
                                                        }
                                                    }}
                                                >
                                                    {segments}
                                                </span>
                                                {" "}
                                            </React.Fragment>
                                        );
                                    };

                                    return renderLineContent();
                                })}

                            </div>

                            {/* Page Footnotes */}
                            {
                                page.footnotes.length > 0 && (
                                    <div className="mt-auto border-t border-slate-300 pt-4 text-sm">
                                        <div className="space-y-1">
                                            {page.footnotes.sort((a, b) => {
                                                if (a.line_no !== b.line_no) return a.line_no - b.line_no;
                                                return a.index - b.index;
                                            }).map((fn, i) => {
                                                const sigla = siglas[fn.nusha_index] || (fn.nusha_index === 1 ? "A" : fn.nusha_index === 2 ? "B" : fn.nusha_index === 3 ? "C" : "D");
                                                let content = "";
                                                if (fn.type === "variation") content = ` : ${fn.content}`;
                                                if (fn.type === "omission") content = ` - ${fn.content}`;
                                                if (fn.type === "addition") content = ` + ${fn.content}`;

                                                const fnNum = footnoteNumbers.get(fn.id) || 0;

                                                return (
                                                    <div key={fn.id} className="flex items-start gap-1 group leading-normal">
                                                        <span className="font-bold text-xs text-slate-500 w-6 text-left pt-1">
                                                            {/* Global index or per page? Usually per page or continuous. Let's do simple index for now. 
                                                    Actually, footnote markers in text were [1], [2] etc relative to line? 
                                                    No, the logic in text use `idx + 1` which is relative to line.
                                                    Here we might want to just show the content or a matching number.
                                                    The text logic `[idx + 1]` is definitely per-line.
                                                    Standard academic usually is per-page continuous.
                                                    For now, let's just show the footnote content without a specific number matching the text one unless we calculate it.
                                                 */}
                                                            {fnNum}
                                                        </span>
                                                        <span
                                                            className="font-serif dir-rtl text-slate-800 cursor-pointer hover:bg-slate-50 rounded px-1 -mx-1"
                                                            onClick={() => {
                                                                setEditingFootnote(fn);
                                                                setMenuInput(fn.content);
                                                            }}
                                                        >
                                                            <span className="font-bold text-amber-700">{sigla}</span>
                                                            {content}
                                                        </span>
                                                        <button
                                                            onClick={async () => {
                                                                // 1. Visually remove immediately
                                                                setPendingDeletes(prev => {
                                                                    const next = new Set(prev);
                                                                    next.add(fn.id);
                                                                    return next;
                                                                });

                                                                // 2. Start delayed delete
                                                                const timer = setTimeout(async () => {
                                                                    await deleteFootnote(fn.id);
                                                                    // Cleanup pending list (though it's gone from main list now)
                                                                    setPendingDeletes(prev => {
                                                                        const next = new Set(prev);
                                                                        next.delete(fn.id);
                                                                        return next;
                                                                    });
                                                                    setLastDeleted(prev => (prev?.fn.id === fn.id ? null : prev));
                                                                }, 5000);

                                                                // 3. Show undo toast
                                                                setLastDeleted({ fn, timeoutId: timer });
                                                                setCountdown(5);
                                                            }}
                                                            className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-400 hover:text-red-500 transition-opacity ml-1"
                                                        >
                                                            <Trash2 size={12} />
                                                        </button>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )
                            }
                        </div>
                    </div>
                ))}

                {/* Undo Toast */}
                {lastDeleted && (
                    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-4 py-2 rounded shadow-lg flex items-center gap-3 animate-in slide-in-from-bottom-5 duration-200 z-50">
                        <span className="text-sm">Dipnot silindi ({countdown} sn).</span>
                        <button
                            onClick={() => {
                                clearTimeout(lastDeleted.timeoutId);
                                setPendingDeletes(prev => {
                                    const next = new Set(prev);
                                    next.delete(lastDeleted.fn.id);
                                    return next;
                                });
                                setLastDeleted(null);
                            }}
                            className="text-amber-400 font-bold text-sm hover:underline"
                        >
                            Geri Al
                        </button>
                        <button onClick={() => {
                            clearTimeout(lastDeleted.timeoutId);
                            setLastDeleted(null);
                        }} className="opacity-50 hover:opacity-100 ml-2">
                            <X size={14} />
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
