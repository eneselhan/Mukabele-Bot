

"use client";

import React, { useRef, useEffect, useState, useMemo, useCallback } from "react";
import { useMukabele, PageData, LineData } from "./MukabeleContext";
import { useParams } from "next/navigation";

// --- PageLayer Component ---
interface PageLayerProps {
    page: PageData;
    projectId: string;
    nushaIndex: number;
    zoom: number;
    activeLine: number | null;
    setActiveLine: (line: number) => void;
    onVisible: (pageKey: string) => void;
}

const PageLayer = React.memo(({
    page,
    projectId,
    nushaIndex,
    zoom,
    activeLine,
    setActiveLine,
    onVisible
}: PageLayerProps) => {
    const [imgLoaded, setImgLoaded] = useState(false);
    const [naturalSize, setNaturalSize] = useState({ w: 0, h: 0 });
    const { mergeLines, lines: allLines } = useMukabele();
    const imgRef = useRef<HTMLImageElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const activeBoxRef = useRef<SVGRectElement>(null);

    // Image URL
    const imageUrl = useMemo(() => {
        if (!page.page_image) return null;
        const rawPath = page.page_image.replace(/\\/g, "/");
        const filename = rawPath.split("/").pop();
        if (!filename) return null;
        const nushaFolder = `nusha_${nushaIndex}`;
        return `http://127.0.0.1:8000/media/${projectId}/${nushaFolder}/pages/${filename}`;
    }, [page, projectId, nushaIndex]);

    const handleImgLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
        const img = e.currentTarget;
        setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
        setImgLoaded(true);
    };

    // Intersection Observer to notify parent when this page is visible
    useEffect(() => {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    onVisible(page.key);
                }
            });
        }, { threshold: 0.5 }); // 50% visible triggers update

        if (containerRef.current) observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, [page.key, onVisible]);

    // Scroll to active line logic
    // We only scroll if this page contains the active line AND the line changed recently
    // But parent might handle the main scroll to page. Here we just ensure the line is visible within the page if it's large?
    // Actually, simply relying on parent's scrollIntoView for the page might be enough, 
    // but precise line scrolling is better.
    useEffect(() => {
        if (activeLine !== null && activeBoxRef.current) {
            // Check if activeLine belongs to this page
            const hasLine = page.lines.some(l => l.line_no === activeLine);
            if (hasLine) {
                activeBoxRef.current.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                    inline: "center"
                });
            }
        }
    }, [activeLine, page.lines]);

    const pageLabel = useMemo(() => {
        if (!page.page_name) return "";
        const match = page.page_name.match(/_(\d+[LR])\.png$/i);
        return match ? match[1] : page.page_name.replace(/\.png$/i, "");
    }, [page]);

    return (
        <div
            ref={containerRef}
            className="relative inline-block transition-all duration-200 origin-top rounded-lg overflow-hidden shadow-2xl shadow-black/40 mb-6"
            style={{ width: `${zoom * 100}%` }}
            id={`page-${page.key}`}
        >
            {imageUrl && (
                <img
                    ref={imgRef}
                    src={imageUrl}
                    alt={page.page_name}
                    className="w-full block bg-slate-50"
                    onLoad={handleImgLoad}
                    loading="lazy"
                />
            )}

            {/* SVG Overlay */}
            {imgLoaded && (
                <svg
                    className="absolute top-0 left-0 w-full h-full pointer-events-auto"
                    viewBox={`0 0 ${naturalSize.w} ${naturalSize.h}`}
                >
                    <defs>
                        <mask id={`mask-${page.key}`}>
                            <rect x="0" y="0" width="100%" height="100%" fill="white" />
                            {activeLine !== null && page.lines.map(line => {
                                if (line.line_no === activeLine && line.bbox) {
                                    const [x0, y0, x1, y1] = line.bbox;
                                    return (
                                        <rect
                                            key={`hole-${line.line_no}`}
                                            x={x0} y={y0}
                                            width={x1 - x0} height={y1 - y0}
                                            fill="black"
                                            rx="10" ry="10"
                                        />
                                    );
                                }
                                return null;
                            })}
                        </mask>
                    </defs>

                    {/* Clickable line rects */}
                    {page.lines.map((line, idx) => {
                        if (!line.bbox) return null;
                        const [x0, y0, x1, y1] = line.bbox;
                        const isFirstOfPage = idx === 0;

                        return (
                            <g key={line.line_no}>
                                <rect
                                    x={x0} y={y0}
                                    width={x1 - x0} height={y1 - y0}
                                    fill="transparent"
                                    className="cursor-pointer hover:fill-amber-500/10"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setActiveLine(line.line_no);
                                    }}
                                >
                                    <title>Satır {line.line_no}</title>
                                </rect>

                                <text
                                    x={x1} y={y1 - ((y1 - y0) * 0.15)}
                                    textAnchor="end"
                                    fontSize={(y1 - y0) * 0.75}
                                    fill="transparent"
                                    stroke="none"
                                    className="pointer-events-none select-none"
                                    style={{
                                        fontFamily: '"Traditional Arabic", serif',
                                        direction: "rtl",
                                        userSelect: "none"
                                    }}
                                >
                                    {line.best?.raw}
                                </text>
                            </g>
                        );
                    })}

                    {/* Dimming overlay (Only if this page has the active line) */}
                    {activeLine !== null && page.lines.some(l => l.line_no === activeLine) && (
                        <rect
                            x="0" y="0" width="100%" height="100%"
                            fill="rgba(0,0,0,0.4)"
                            mask={`url(#mask-${page.key})`}
                            className="pointer-events-none"
                        />
                    )}

                    {/* Active line stroke */}
                    {activeLine !== null && page.lines.map(line => {
                        if (line.line_no === activeLine && line.bbox) {
                            const [x0, y0, x1, y1] = line.bbox;
                            return (
                                <rect
                                    ref={activeBoxRef}
                                    key={`outline-${line.line_no}`}
                                    x={x0} y={y0}
                                    width={x1 - x0} height={y1 - y0}
                                    fill="none"
                                    stroke="#f59e0b"
                                    strokeWidth="6"
                                    rx="10" ry="10"
                                    className="pointer-events-none transition-all duration-300"
                                />
                            );
                        }
                        return null;
                    })}
                </svg>
            )}

            {pageLabel && (
                <div className="absolute bottom-3 left-3 bg-white/90 backdrop-blur-sm text-slate-700 text-xs font-bold px-2.5 py-1 rounded-lg border border-slate-200 shadow-sm">
                    {pageLabel}
                </div>
            )}
        </div>
    );
});
PageLayer.displayName = "PageLayer";


// --- Main PageCanvas ---
export default function PageCanvas() {
    const {
        pages,
        activePageKey, setActivePageKey,
        zoom,
        activeLine,
        setActiveLine,
        nushaIndex
    } = useMukabele();

    const params = useParams();
    const projectId = params.id as string;
    const containerRef = useRef<HTMLDivElement>(null);
    const thumbnailsRef = useRef<HTMLDivElement>(null);

    // Track manually triggered scroll to avoid fighting IntersectionObserver
    const isScrollingRef = useRef(false);

    // Callback when a page becomes visible
    const onPageVisible = useCallback((pageKey: string) => {
        if (isScrollingRef.current) return;
        setActivePageKey(pageKey);
    }, [setActivePageKey]);

    // Scroll Thumbnail Strip when activePageKey changes
    useEffect(() => {
        if (!activePageKey || !thumbnailsRef.current) return;

        const activeThumb = document.getElementById(`thumb-${activePageKey}`);
        if (activeThumb) {
            activeThumb.scrollIntoView({
                behavior: "smooth",
                block: "nearest",
                inline: "center"
            });
        }
    }, [activePageKey]);

    // Sync: Scroll list to page when activePageKey changes manually (e.g. thumb click)
    // We need to differentiate between user scrolling (Intersection) and thumb click.
    // We can use a separate mechanism or just check if it's already visible.
    // For now, let's assume if the User clicked a thumbnail, we want to scroll there.
    // But wait, IntersectionObserver sets activePageKey too. cyclic?
    // No, onPageVisible checks isScrollingRef.

    // Actually, handling "User clicked thumbnail" is better done in the click handler.
    const handleThumbClick = (key: string) => {
        isScrollingRef.current = true;
        setActivePageKey(key);

        const pageEl = document.getElementById(`page-${key}`);
        if (pageEl) {
            pageEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }

        // Reset scrolling lock after animation
        setTimeout(() => {
            isScrollingRef.current = false;
        }, 800);
    };

    return (
        <div className="flex flex-col h-full bg-white border-r border-slate-200">
            {/* Main scrollable list */}
            <div
                ref={containerRef}
                className="flex-1 overflow-auto relative text-center p-3 flex flex-col items-center"
            >
                <div className="flex flex-col items-center pb-20 w-full">
                    {pages.map(page => (
                        <PageLayer
                            key={page.key}
                            page={page}
                            projectId={projectId}
                            nushaIndex={nushaIndex}
                            zoom={zoom}
                            activeLine={activeLine}
                            setActiveLine={setActiveLine}
                            onVisible={onPageVisible}
                        />
                    ))}
                </div>
            </div>

            {/* Thumbnail strip */}
            <div
                ref={thumbnailsRef}
                className="shrink-0 bg-slate-850 border-t border-slate-700 px-2 py-1.5 overflow-x-auto flex gap-1.5 items-center scrollbar-thin scrollbar-thumb-slate-700"
                style={{ backgroundColor: "rgb(22, 28, 38)" }}
            >
                {pages.map((page, idx) => {
                    const isActive = page.key === activePageKey;
                    const rawPath = page.page_image?.replace(/\\/g, "/");
                    const fname = rawPath?.split("/").pop();
                    const thumbUrl = fname
                        ? `http://127.0.0.1:8000/media/${projectId}/nusha_${nushaIndex}/pages/${fname}`
                        : null;

                    const label = page.page_name?.match(/_(\d+[LR])\.png$/i)?.[1] || `${idx + 1}`;

                    return (
                        <button
                            key={page.key}
                            id={`thumb-${page.key}`}
                            onClick={() => handleThumbClick(page.key)}
                            className={`shrink-0 flex flex-col items-center gap-0.5 rounded-md p-0.5 transition-all ${isActive
                                ? "ring-2 ring-amber-500 bg-slate-700"
                                : "hover:bg-slate-700/50 opacity-60 hover:opacity-100"
                                }`}
                            title={page.page_name}
                        >
                            {thumbUrl ? (
                                <img
                                    src={thumbUrl}
                                    alt={label}
                                    className="h-10 w-auto rounded object-contain bg-slate-950"
                                    loading="lazy"
                                />
                            ) : (
                                <div className="h-10 w-8 bg-slate-700 rounded flex items-center justify-center text-[9px] text-slate-400">
                                    {idx + 1}
                                </div>
                            )}
                            <span className={`text-[8px] font-medium tabular-nums ${isActive ? "text-amber-400" : "text-slate-500"}`}>
                                {label}
                            </span>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
