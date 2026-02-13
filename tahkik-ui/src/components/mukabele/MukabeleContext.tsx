"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";

// Types
export interface LineData {
    line_no: number;
    text?: string;
    best?: {
        raw: string;
        start_word?: number;
        end_word?: number;
    };
    page_image?: string;
    page_name?: string;
    bbox?: number[]; // [x0, y0, x1, y1]
    line_marks?: any[]; // Spellcheck errors
    ocr_text?: string; // Aligned OCR text
    image_url?: string; // OCR line image URL
    // ... add other fields as needed
}

export interface Footnote {
    id: string;
    line_no: number;
    index: number; // char index in line
    type: "variation" | "omission" | "addition";
    nusha_index: number;
    content: string;
}

export interface MukabeleData {
    aligned: LineData[]; // Nusha 1 (Primary)
    aligned_alt?: LineData[]; // Nusha 2
    aligned_alt3?: LineData[]; // Nusha 3
    aligned_alt4?: LineData[]; // Nusha 4
    has_alt?: boolean;
    has_alt3?: boolean;
    has_alt4?: boolean;
    default_nusha?: number;
    nusha_siglas?: { [key: string]: string };
    nusha_names?: { [key: string]: string };
    base_nusha_index?: number;
    footnotes?: Footnote[];
    // ... spellcheck data, etc.
}

interface MukabeleContextType {
    // Data
    data: MukabeleData | null;
    setData: (data: MukabeleData) => void;
    isLoading: boolean;
    setIsLoading: (loading: boolean) => void;

    // View State
    activeLine: number | null;
    setActiveLine: (lineNo: number | null) => void;
    activePageKey: string | null;
    setActivePageKey: (key: string | null) => void;

    // Footnotes
    footnotes: Footnote[];
    addFootnote: (footnote: Footnote) => Promise<void>;
    deleteFootnote: (id: string) => Promise<void>;
    updateFootnote: (id: string, newContent: string) => Promise<void>;

    // Search
    searchQuery: string;
    setSearchQuery: (query: string) => void;
    searchMatches: number[]; // Line numbers
    currentSearchIndex: number;
    nextSearch: () => void;
    prevSearch: () => void;

    // Popup
    errorPopupData: any | null;
    setErrorPopupData: (data: any | null) => void;

    // UI State
    zoom: number;
    setZoom: (zoom: number) => void; // 1.0 to 5.0
    splitRatio: number;
    setSplitRatio: (ratio: number) => void; // 0.2 to 0.8
    fontSize: number;
    setFontSize: (size: number) => void; // px
    viewMode: 'list' | 'paper';
    setViewMode: (mode: 'list' | 'paper') => void;

    // Nusha State
    nushaIndex: number;
    setNushaIndex: (index: number) => void; // 1, 2, 3, 4
    baseNushaIndex: number;
    updateBaseNusha: (index: number) => Promise<void>;
    siglas: { [key: string]: string };
    updateSigla: (nushaIndex: number, sigla: string) => Promise<void>;

    // Helpers
    lines: LineData[]; // Returns active lines
    pages: PageData[]; // Derived pages index
    updateLineText: (lineNo: number, newText: string) => void;
    deleteLine: (lineNo: number) => Promise<boolean>;
    mergeLines: (nushaIndex: number, lineNumbers: number[]) => Promise<void>;

    setPages: (pages: PageData[]) => void;
}

export interface PageData {
    key: string;
    lines: LineData[];
    page_image: string;
    page_name: string;
}

const MukabeleContext = createContext<MukabeleContextType | undefined>(undefined);

export function MukabeleProvider({ children }: { children: React.ReactNode }) {
    // State
    const [data, setData] = useState<MukabeleData | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [pages, setPages] = useState<PageData[]>([]);

    const [activeLine, setActiveLine] = useState<number | null>(null);
    const [activePageKey, setActivePageKey] = useState<string | null>(null);
    const activePageKeyRef = React.useRef<string | null>(null);


    const [zoom, setZoomState] = useState(1.32);
    const [splitRatio, setSplitRatioState] = useState(0.52);
    const [fontSize, setFontSizeState] = useState(23);
    const [viewMode, setViewModeState] = useState<'list' | 'paper'>('list');
    const [nushaIndex, setNushaIndexState] = useState(1);
    const [baseNushaIndex, setBaseNushaIndex] = useState(1);
    const [siglas, setSiglas] = useState<{ [key: string]: string }>({});

    // Footnotes
    const [footnotes, setFootnotes] = useState<Footnote[]>([]);

    // Load initial data
    useEffect(() => {
        if (!data) return;
        if (data.footnotes) {
            setFootnotes(data.footnotes);
        }
    }, [data]);

    // Save footnotes
    const saveFootnotes = async (newFootnotes: Footnote[]) => {
        if (!projectId) return;
        try {
            await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/footnotes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ footnotes: newFootnotes })
            });
        } catch (e) {
            console.error("Failed to save footnotes", e);
        }
    };

    const addFootnote = async (footnote: Footnote) => {
        const updated = [...footnotes, footnote];
        setFootnotes(updated);
        await saveFootnotes(updated);
    };

    const deleteFootnote = async (id: string) => {
        const updated = footnotes.filter(f => f.id !== id);
        setFootnotes(updated);
        await saveFootnotes(updated);
    };

    const updateFootnote = async (id: string, newContent: string) => {
        const updated = footnotes.map(f => f.id === id ? { ...f, content: newContent } : f);
        setFootnotes(updated);
        await saveFootnotes(updated);
    };

    // Search
    const [searchQuery, setSearchQuery] = useState("");
    const [searchMatches, setSearchMatches] = useState<number[]>([]);
    const [currentSearchIndex, setCurrentSearchIndex] = useState(-1);

    // Popup
    const [errorPopupData, setErrorPopupData] = useState<any | null>(null);

    // Load saved preferences
    useEffect(() => {
        try {
            const savedZoom = localStorage.getItem("mukabele_zoom");
            if (savedZoom) setZoomState(parseFloat(savedZoom));

            const savedSplit = localStorage.getItem("mukabele_split");
            if (savedSplit) setSplitRatioState(parseFloat(savedSplit));

            const savedFont = localStorage.getItem("mukabele_font");
            if (savedFont) setFontSizeState(parseInt(savedFont));

            const savedViewMode = localStorage.getItem("mukabele_view_mode");
            if (savedViewMode === 'paper') setViewModeState('paper');
        } catch (e) { }
    }, []);

    // Persistence wrappers
    const setZoom = (z: number) => {
        const val = Math.max(1.0, Math.min(5.0, z));
        setZoomState(val);
        localStorage.setItem("mukabele_zoom", val.toString());
    };

    const setSplitRatio = (r: number) => {
        const val = Math.max(0.18, Math.min(0.82, r));
        setSplitRatioState(val);
        localStorage.setItem("mukabele_split", val.toString());
    };

    const setFontSize = (s: number) => {
        const val = Math.max(12, Math.min(36, s));
        setFontSizeState(val);
        localStorage.setItem("mukabele_font", val.toString());
    };

    const setViewMode = (mode: 'list' | 'paper') => {
        setViewModeState(mode);
        localStorage.setItem("mukabele_view_mode", mode);
    };

    const setNushaIndex = (targetIndex: number) => {
        // 1. Capture current state (Pivot)
        let pivotWord = "";
        let relativePosition = 0; // 0.0 to 1.0

        if (activeLine !== null) {
            // Find current active line object
            let currentLineObj: LineData | undefined;
            let currentLineIdx = -1;

            // Get current lines based on OLD nushaIndex
            let currentLines: LineData[] = [];
            switch (nushaIndex) {
                case 2: currentLines = data?.aligned_alt || []; break;
                case 3: currentLines = data?.aligned_alt3 || []; break;
                case 4: currentLines = data?.aligned_alt4 || []; break;
                default: currentLines = data?.aligned || []; break;
            }

            // Find line index
            currentLineIdx = currentLines.findIndex(l => l.line_no === activeLine);

            if (currentLineIdx !== -1) {
                // Calculate relative position (fallback)
                relativePosition = currentLines.length > 0 ? currentLineIdx / currentLines.length : 0;

                // Attempt to find pivot word
                // If empty, search BACKWARDS
                let searchIdx = currentLineIdx;
                let found = false;

                // Search backwards (including current)
                while (searchIdx >= 0) {
                    const txt = currentLines[searchIdx]?.best?.raw?.trim() || "";
                    if (txt) {
                        const words = txt.split(/\s+/);
                        if (words.length > 0) {
                            pivotWord = words[0]; // Use FIRST word
                            found = true;
                            break;
                        }
                    }
                    searchIdx--;
                }

                // If not found backwards, try forwards (rare edge case: start of doc empty)
                if (!found) {
                    searchIdx = currentLineIdx + 1;
                    while (searchIdx < currentLines.length) {
                        const txt = currentLines[searchIdx]?.best?.raw?.trim() || "";
                        if (txt) {
                            const words = txt.split(/\s+/);
                            if (words.length > 0) {
                                pivotWord = words[0]; // Use FIRST word
                                found = true;
                                break;
                            }
                        }
                        searchIdx++;
                    }
                }
            }
        }

        // 2. Switch Nüsha
        setNushaIndexState(targetIndex);
        if (projectId) localStorage.setItem(`mukabele_${projectId}_nusha`, targetIndex.toString());

        // 3. Find Match in Target Nüsha
        if (pivotWord && data) {
            let targetLines: LineData[] = [];
            switch (targetIndex) {
                case 2: targetLines = data.aligned_alt || []; break;
                case 3: targetLines = data.aligned_alt3 || []; break;
                case 4: targetLines = data.aligned_alt4 || []; break;
                default: targetLines = data.aligned || []; break;
            }

            if (targetLines.length > 0) {
                // Heuristic: Start search from relative position to avoid false positives (e.g. common words)
                const startIdx = Math.floor(targetLines.length * relativePosition);

                // Search outward from startIdx
                let bestMatchLine: number | null = null;
                let minDist = Infinity;

                // Limit search radius for performance (e.g. +/- 50 lines)
                const radius = 50;
                const minI = Math.max(0, startIdx - radius);
                const maxI = Math.min(targetLines.length - 1, startIdx + radius);

                for (let i = minI; i <= maxI; i++) {
                    const txt = targetLines[i]?.best?.raw || "";
                    if (txt.includes(pivotWord)) {
                        // Found a candidate.
                        // Prefer closest to startIdx
                        const dist = Math.abs(i - startIdx);
                        if (dist < minDist) {
                            minDist = dist;
                            bestMatchLine = targetLines[i].line_no;
                            // Optimistic break if very close
                            if (dist === 0) break;
                        }
                    }
                }

                if (bestMatchLine !== null) {
                    // Use setTimeout to allow render cycle to update lines view before scrolling
                    setTimeout(() => setActiveLineWithSync(bestMatchLine), 50);
                } else {
                    // Fallback: Just map by relative index
                    const fallbackLine = targetLines[Math.min(startIdx, targetLines.length - 1)];
                    if (fallbackLine) {
                        setTimeout(() => setActiveLineWithSync(fallbackLine.line_no), 50);
                    }
                }
            }
        }
    };

    const params = useParams();
    const projectId = params?.id as string;

    // Load project-specific preferences
    useEffect(() => {
        if (!projectId) return;

        // Active Nusha
        const savedNusha = localStorage.getItem(`mukabele_${projectId}_nusha`);
        if (savedNusha) {
            const n = parseInt(savedNusha);
            if (!isNaN(n)) setNushaIndexState(n);
        }

        // Active Line
        const savedLine = localStorage.getItem(`mukabele_${projectId}_line`);
        if (savedLine) {
            const l = parseInt(savedLine);
            if (!isNaN(l)) setActiveLine(l);
        }

        // Active Page Key
        const savedPage = localStorage.getItem(`mukabele_${projectId}_page`);
        if (savedPage) {
            setActivePageKey(savedPage);
            activePageKeyRef.current = savedPage;
        }
    }, [projectId]);

    // Persist activeLine
    useEffect(() => {
        if (projectId && activeLine !== null) {
            localStorage.setItem(`mukabele_${projectId}_line`, activeLine.toString());
        }
    }, [projectId, activeLine]);

    // Persist activePageKey
    useEffect(() => {
        if (projectId && activePageKey) {
            localStorage.setItem(`mukabele_${projectId}_page`, activePageKey);
            activePageKeyRef.current = activePageKey;
        }
    }, [projectId, activePageKey]);

    // Update a specific line's text in local state (called after successful save)
    const updateLineText = (lineNo: number, newText: string) => {
        // Update in data state
        if (data) {
            const newData = { ...data };
            const keys: (keyof MukabeleData)[] = ['aligned', 'aligned_alt', 'aligned_alt3', 'aligned_alt4'];
            for (const key of keys) {
                const arr = newData[key] as LineData[] | undefined;
                if (arr) {
                    const line = arr.find(l => l.line_no === lineNo);
                    if (line) {
                        if (line.best) {
                            line.best = { ...line.best, raw: newText };
                        } else {
                            line.best = { raw: newText };
                        }
                        break;
                    }
                }
            }
            setData(newData);
        }

        // Update in pages state
        setPages(prev => prev.map(page => ({
            ...page,
            lines: page.lines.map(l => {
                if (l.line_no === lineNo) {
                    return {
                        ...l,
                        best: { ...(l.best || { raw: '' }), raw: newText }
                    };
                }
                return l;
            })
        })));
    };

    // Delete a line from backend and local state
    const deleteLine = useCallback(async (lineNo: number): Promise<boolean> => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/lines/delete`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ line_no: lineNo, nusha_index: nushaIndex })
            });
            if (!res.ok) return false;

            // Remove from local data state
            if (data) {
                const newData = { ...data };
                const keys: (keyof MukabeleData)[] = ['aligned', 'aligned_alt', 'aligned_alt3', 'aligned_alt4'];
                for (const key of keys) {
                    const arr = newData[key] as LineData[] | undefined;
                    if (arr) {
                        (newData as any)[key] = arr.filter(l => l.line_no !== lineNo);
                    }
                }
                setData(newData);
            }

            // Remove from pages state
            setPages(prev => prev.map(page => ({
                ...page,
                lines: page.lines.filter(l => l.line_no !== lineNo)
            })));

            // If deleted line was active, clear selection
            if (activeLine === lineNo) {
                setActiveLine(null);
            }

            return true;
        } catch (err) {
            console.error("Delete line error:", err);
            return false;
        }
    }, [projectId, nushaIndex, data, activeLine]);

    // Update Sigla
    const updateSigla = useCallback(async (nIndex: number, sigla: string) => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/sigla`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ nusha_index: nIndex, sigla })
            });
            if (res.ok) {
                setSiglas(prev => ({ ...prev, [nIndex]: sigla }));
            }
        } catch (e) {
            console.error("Failed to update sigla", e);
        }
    }, [projectId]);

    // Update Base Nusha
    const updateBaseNusha = useCallback(async (index: number) => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/base-nusha`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ nusha_index: index })
            });
            if (res.ok) {
                setBaseNushaIndex(index);
                setNushaIndex(index); // Auto-switch view
            }
        } catch (e) {
            console.error("Failed to update base nusha", e);
        }
    }, [projectId, setNushaIndex]);

    // Derived Data
    const lines = React.useMemo(() => {
        if (!data) return [];
        switch (nushaIndex) {
            case 2: return data.aligned_alt || [];
            case 3: return data.aligned_alt3 || [];
            case 4: return data.aligned_alt4 || [];
            default: return data.aligned || [];
        }
    }, [data, nushaIndex]);

    // LOAD DATA FUNCTION
    const fetchData = useCallback(async () => {
        const pId = projectId;
        if (!pId) return;

        setIsLoading(true);
        try {
            // 1. Fetch Alignment Data
            const resData = await fetch(`http://127.0.0.1:8000/api/projects/${pId}/mukabele-data`);
            if (!resData.ok) {
                // Try to handle non-ok by setting empty data or throwing
                throw new Error("Alignment data fetch failed");
            }
            const jsonData = await resData.json();
            setData(jsonData);
            // Sigla Initialization
            const serverSiglas = jsonData.nusha_siglas || {};
            const finalSiglas: any = { ...serverSiglas };

            // Fill defaults only if missing
            if (!finalSiglas["1"] && jsonData.aligned) finalSiglas["1"] = "A";
            if (!finalSiglas["2"] && jsonData.aligned_alt) finalSiglas["2"] = "B";
            if (!finalSiglas["3"] && jsonData.aligned_alt3) finalSiglas["3"] = "C";
            if (!finalSiglas["4"] && jsonData.aligned_alt4) finalSiglas["4"] = "D";

            setSiglas(finalSiglas);

            if (jsonData.base_nusha_index) {
                setBaseNushaIndex(jsonData.base_nusha_index);
                // Sync view if not locally overridden
                // We check if localStorage has a value for this project
                if (!localStorage.getItem(`mukabele_${pId}_nusha`)) {
                    setNushaIndexState(jsonData.base_nusha_index);
                }
            }

            // 2. Fetch Pages
            const resPages = await fetch(`http://127.0.0.1:8000/api/projects/${pId}/pages?nusha_index=${nushaIndex}`);
            if (resPages.ok) {
                const pagesData = await resPages.json();

                // Map API pages to Frontend Pages
                const newPages: PageData[] = pagesData.map((p: any) => ({
                    key: p.key,
                    page_image: p.image_filename,
                    page_name: `Sayfa ${p.index + 1}`,
                    lines: []
                }));

                // Distribute lines to pages
                let currentLines: LineData[] = [];
                switch (nushaIndex) {
                    case 2: currentLines = jsonData.aligned_alt || []; break;
                    case 3: currentLines = jsonData.aligned_alt3 || []; break;
                    case 4: currentLines = jsonData.aligned_alt4 || []; break;
                    default: currentLines = jsonData.aligned || []; break;
                }

                currentLines.forEach(line => {
                    if (!line.page_image) return;

                    // Normalize filenames for comparison (handle paths vs filenames)
                    const linePageName = line.page_image.replace(/\\/g, "/").split("/").pop();

                    const target = newPages.find(p => {
                        const pPageName = p.page_image.replace(/\\/g, "/").split("/").pop();
                        return pPageName === linePageName;
                    });

                    if (target) {
                        target.lines.push(line);
                    }
                });

                setPages(newPages);

                // Set initial active page if none
                if (newPages.length > 0 && !activePageKeyRef.current) {
                    const firstKey = newPages[0].key;
                    setActivePageKey(firstKey);
                    activePageKeyRef.current = firstKey;
                }
            } else {
                setPages([]);
            }

            setIsLoading(false);
        } catch (err) {
            console.error("Data load error:", err);
            setIsLoading(false);
        }
    }, [projectId, nushaIndex]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Search Logic
    useEffect(() => {
        if (!searchQuery.trim()) {
            setSearchMatches([]);
            setCurrentSearchIndex(-1);
            return;
        }
        const normalize = (s: string) => s.replace(/[\u064B-\u065F\u0670]/g, "").replace(/[^\u0600-\u06FF]/g, "");
        const q = normalize(searchQuery);
        if (!q) return;

        const matches: number[] = [];
        lines.forEach(l => {
            const raw = l.best?.raw || "";
            const norm = normalize(raw);
            if (norm.includes(q)) {
                matches.push(l.line_no);
            }
        });
        setSearchMatches(matches);
        setCurrentSearchIndex(matches.length ? 0 : -1);
        if (matches.length > 0) {
            setActiveLine(matches[0]); // Don't force sync on load, just set line
        }
    }, [searchQuery, lines]);

    const nextSearch = () => {
        if (!searchMatches.length) return;
        const next = (currentSearchIndex + 1) % searchMatches.length;
        setCurrentSearchIndex(next);
        setActiveLineWithSync(searchMatches[next]);
    };

    const prevSearch = () => {
        if (!searchMatches.length) return;
        const prev = (currentSearchIndex - 1 + searchMatches.length) % searchMatches.length;
        setCurrentSearchIndex(prev);
        setActiveLineWithSync(searchMatches[prev]);
    };

    // Explicitly sync page when active line is set by user action
    const setActiveLineWithSync = (lineNo: number | null) => {
        setActiveLine(lineNo);
        if (lineNo !== null && pages.length > 0) {
            const line = lines.find(l => l.line_no === lineNo);
            if (line) {
                const pimg = line.page_image || "";
                const foundPage = pages.find(p => p.page_image === (pimg.replace(/\\/g, "/").split("/").pop()));
                if (foundPage && foundPage.key !== activePageKey) {
                    setActivePageKey(foundPage.key);
                }
            }
        }
    };

    // ── Keyboard Shortcuts ──
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Skip if user is typing in an editable field
            const tag = (e.target as HTMLElement)?.tagName;
            const isEditable = (e.target as HTMLElement)?.isContentEditable;
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || isEditable) {
                // Only intercept Ctrl+S inside editable fields
                if (e.ctrlKey && e.key === "s") {
                    e.preventDefault();
                }
                return;
            }

            // Ctrl+S: prevent default browser save
            if (e.ctrlKey && e.key === "s") {
                e.preventDefault();
                return;
            }

            // Arrow Up / Down: navigate lines
            if (e.key === "ArrowUp" || e.key === "ArrowDown") {
                e.preventDefault();
                const currentPage = pages.find(p => p.key === activePageKeyRef.current);
                if (!currentPage || !currentPage.lines.length) return;
                const pageLines = currentPage.lines;
                const currentIdx = pageLines.findIndex(l => l.line_no === activeLine);

                if (e.key === "ArrowUp") {
                    const prev = currentIdx > 0 ? currentIdx - 1 : 0;
                    setActiveLineWithSync(pageLines[prev].line_no);
                } else {
                    const next = currentIdx < pageLines.length - 1 ? currentIdx + 1 : pageLines.length - 1;
                    setActiveLineWithSync(pageLines[next].line_no);
                }
                return;
            }

            // Arrow Left / Right: navigate pages
            if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                const pageIdx = pages.findIndex(p => p.key === activePageKeyRef.current);
                if (e.key === "ArrowLeft" && pageIdx > 0) {
                    setActivePageKey(pages[pageIdx - 1].key);
                } else if (e.key === "ArrowRight" && pageIdx < pages.length - 1) {
                    setActivePageKey(pages[pageIdx + 1].key);
                }
                return;
            }

            // E: jump to next error line
            if (e.key === "e" || e.key === "E") {
                const errorLineNos = lines
                    .filter(l => l.line_marks && l.line_marks.length > 0)
                    .map(l => l.line_no);
                if (!errorLineNos.length) return;
                const currentIdx = errorLineNos.indexOf(activeLine ?? -1);
                const nextIdx = (currentIdx + 1) % errorLineNos.length;
                setActiveLineWithSync(errorLineNos[nextIdx]);
                return;
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [pages, activeLine, lines]);

    // Effect: Removed automatic sync to prevent reverts on autosave.
    // Page sync is now handled explicitly by setActiveLineWithSync.

    const mergeLines = async (nushaIndex: number, lineNumbers: number[]) => {
        if (!projectId) return;
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/projects/${projectId}/lines/merge`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nusha_index: nushaIndex, line_numbers: lineNumbers })
            });
            if (res.ok) {
                fetchData();
            }
        } catch (e) {
            console.error("Merge lines failed", e);
        }
    };



    const value = {
        data, setData,
        isLoading, setIsLoading,
        lines,
        pages,
        activeLine, setActiveLine: setActiveLineWithSync,
        activePageKey, setActivePageKey,
        zoom, setZoom,
        fontSize, setFontSize,
        viewMode, setViewMode,
        searchQuery, setSearchQuery,
        searchMatches, currentSearchIndex,
        nextSearch, prevSearch,
        errorPopupData, setErrorPopupData,
        nushaIndex, setNushaIndex,
        baseNushaIndex, updateBaseNusha,
        splitRatio, setSplitRatio,
        updateLineText,
        deleteLine,
        mergeLines,

        setPages,
        siglas, updateSigla,
        footnotes, addFootnote, deleteFootnote, updateFootnote,
    };

    return (
        <MukabeleContext.Provider value={value}>
            {children}
        </MukabeleContext.Provider>
    );
}

export function useMukabele() {
    const context = useContext(MukabeleContext);
    if (context === undefined) {
        throw new Error("useMukabele must be used within a MukabeleProvider");
    }
    return context;
}
