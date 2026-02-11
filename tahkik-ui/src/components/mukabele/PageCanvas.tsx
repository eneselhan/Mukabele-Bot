"use client";

import React, { useRef, useEffect, useState, useMemo } from "react";
import { useMukabele } from "./MukabeleContext";
import { useParams } from "next/navigation";

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

    const [imgLoaded, setImgLoaded] = useState(false);
    const [naturalSize, setNaturalSize] = useState({ w: 0, h: 0 });
    const containerRef = useRef<HTMLDivElement>(null);
    const activeBoxRef = useRef<SVGRectElement>(null);

    const currentPage = useMemo(() => {
        return pages.find(p => p.key === activePageKey);
    }, [pages, activePageKey]);

    useEffect(() => {
        setImgLoaded(false);
    }, [activePageKey, nushaIndex]);

    const imageUrl = useMemo(() => {
        if (!currentPage?.page_image) return null;
        const rawPath = currentPage.page_image.replace(/\\/g, "/");
        const filename = rawPath.split("/").pop();
        if (!filename) return null;
        const nushaFolder = `nusha_${nushaIndex}`;
        return `http://localhost:8000/media/${projectId}/${nushaFolder}/pages/${filename}`;
    }, [currentPage, projectId, nushaIndex, activePageKey]);

    const handleImgLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
        const img = e.currentTarget;
        setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
        setImgLoaded(true);
    };

    // Auto-scroll to active bbox
    useEffect(() => {
        if (activeLine !== null && activeBoxRef.current && containerRef.current) {
            setTimeout(() => {
                activeBoxRef.current?.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                    inline: "center"
                });
            }, 100);
        }
    }, [activeLine, zoom, naturalSize]);

    // Extract page label from page_name (e.g. "page_0001_01R.png" → "01R")
    const pageLabel = useMemo(() => {
        if (!currentPage?.page_name) return "";
        const match = currentPage.page_name.match(/_(\d+[LR])\.png$/i);
        return match ? match[1] : currentPage.page_name.replace(/\.png$/i, "");
    }, [currentPage]);

    if (!currentPage) {
        return (
            <div className="flex items-center justify-center h-full text-slate-500 bg-slate-900">
                <span className="text-sm">Sayfa seçili değil</span>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-slate-900">
            {/* Main canvas area */}
            <div
                ref={containerRef}
                className="flex-1 overflow-auto relative text-center p-3"
            >
                <div
                    className="relative inline-block transition-all duration-200 origin-top rounded-lg overflow-hidden shadow-2xl shadow-black/40"
                    style={{ width: `${zoom * 100}%` }}
                >
                    {imageUrl && (
                        <img
                            src={imageUrl}
                            alt={currentPage.page_name}
                            className="w-full block"
                            onLoad={handleImgLoad}
                        />
                    )}

                    {/* SVG Overlay */}
                    {imgLoaded && (
                        <svg
                            className="absolute top-0 left-0 w-full h-full pointer-events-auto"
                            viewBox={`0 0 ${naturalSize.w} ${naturalSize.h}`}
                        >
                            <defs>
                                <mask id="highlightMask">
                                    <rect x="0" y="0" width="100%" height="100%" fill="white" />
                                    {activeLine !== null && currentPage.lines.map(line => {
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
                            {currentPage.lines.map(line => {
                                if (!line.bbox) return null;
                                const [x0, y0, x1, y1] = line.bbox;
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

                            {/* Dimming overlay */}
                            {activeLine !== null && (
                                <rect
                                    x="0" y="0" width="100%" height="100%"
                                    fill="rgba(0,0,0,0.4)"
                                    mask="url(#highlightMask)"
                                    className="pointer-events-none"
                                />
                            )}

                            {/* Active line stroke */}
                            {activeLine !== null && currentPage.lines.map(line => {
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

                    {/* Page label overlay */}
                    {pageLabel && (
                        <div className="absolute bottom-3 left-3 bg-black/60 backdrop-blur-sm text-white text-xs font-bold px-2.5 py-1 rounded-lg border border-white/10">
                            {pageLabel}
                        </div>
                    )}
                </div>
            </div>

            {/* Thumbnail strip */}
            <div className="shrink-0 bg-slate-850 border-t border-slate-700 px-2 py-1.5 overflow-x-auto flex gap-1.5 items-center"
                style={{ backgroundColor: "rgb(22, 28, 38)" }}
            >
                {pages.map((page, idx) => {
                    const isActive = page.key === activePageKey;
                    const rawPath = page.page_image?.replace(/\\/g, "/");
                    const fname = rawPath?.split("/").pop();
                    const thumbUrl = fname
                        ? `http://localhost:8000/media/${projectId}/nusha_${nushaIndex}/pages/${fname}`
                        : null;

                    // Extract short label
                    const label = page.page_name?.match(/_(\d+[LR])\.png$/i)?.[1] || `${idx + 1}`;

                    return (
                        <button
                            key={page.key}
                            onClick={() => setActivePageKey(page.key)}
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
