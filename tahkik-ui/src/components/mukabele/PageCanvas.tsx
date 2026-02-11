"use client";

import React, { useRef, useEffect, useState, useMemo } from "react";
import { useMukabele } from "./MukabeleContext";
import { useParams } from "next/navigation";

export default function PageCanvas() {
    const {
        pages,
        activePageKey,
        zoom,
        activeLine,
        setActiveLine,
        nushaIndex
    } = useMukabele();

    // We need usage of useParams to get project ID for image URLs
    const params = useParams(); // params.id is project_id
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

    // Construct Image URL
    const imageUrl = useMemo(() => {
        if (!currentPage?.page_image) {
            console.log("PageCanvas: No currentPage or page_image", { currentPage, activePageKey });
            return null;
        }

        const rawPath = currentPage.page_image.replace(/\\/g, "/");
        const filename = rawPath.split("/").pop();

        if (!filename) return null;

        // Determine subfolder based on Nusha Index
        // nushaIndex: 1 -> nusha_1, 2 -> nusha_2, etc.
        const nushaFolder = `nusha_${nushaIndex}`;

        // Construct URL: /media/{projectId}/{nushaFolder}/pages/{filename}
        const url = `http://localhost:8000/media/${projectId}/${nushaFolder}/pages/${filename}`;

        console.log("PageCanvas: Constructed URL", url);
        return url;
    }, [currentPage, projectId, nushaIndex, activePageKey]);

    const handleImgLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
        const img = e.currentTarget;
        setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
        setImgLoaded(true);
    };

    // Auto-scroll to active bbox
    useEffect(() => {
        if (activeLine !== null && activeBoxRef.current && containerRef.current) {
            // Wait for render?
            setTimeout(() => {
                if (activeBoxRef.current && containerRef.current) {
                    const box = activeBoxRef.current.getBoundingClientRect();
                    const cont = containerRef.current.getBoundingClientRect();

                    // Helper to scroll
                    const scrollTop = activeBoxRef.current.getBBox().y * (containerRef.current.clientWidth / naturalSize.w) * zoom; // Rough estimate or use scrollIntoView

                    activeBoxRef.current.scrollIntoView({
                        behavior: "smooth",
                        block: "center",
                        inline: "center"
                    });
                }
            }, 100);
        }
    }, [activeLine, zoom, naturalSize]);

    if (!currentPage) {
        return (
            <div className="flex items-center justify-center h-full text-slate-400">
                Sayfa seçili değil
            </div>
        );
    }

    return (
        <div
            ref={containerRef}
            className="w-full h-full overflow-auto bg-slate-100 relative text-center p-4"
        >
            <div
                className="relative inline-block transition-all duration-200 origin-top rounded shadow-sm border border-slate-200 overflow-hidden"
                style={{
                    width: `${zoom * 100}%`,
                }}
            >
                {/* Image */}
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
                        {/* Mask Definition for Darkening */}
                        <defs>
                            <mask id="highlightMask">
                                <rect x="0" y="0" width="100%" height="100%" fill="white" />
                                {/* Cut hole for active line */}
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

                        {/* Clickable transparent rects & OCR Text for ALL lines */}
                        {currentPage.lines.map(line => {
                            if (!line.bbox) return null;
                            const [x0, y0, x1, y1] = line.bbox;
                            const width = x1 - x0;
                            const height = y1 - y0;
                            // Calculate font size to fit height roughly
                            const fontSize = height * 0.75;

                            return (
                                <g key={line.line_no}>
                                    {/* Invisible Rect for click hit area */}
                                    <rect
                                        x={x0} y={y0}
                                        width={width} height={height}
                                        fill="transparent"
                                        className="cursor-pointer hover:fill-blue-500/10"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setActiveLine(line.line_no);
                                        }}
                                    >
                                        <title>Satır {line.line_no}</title>
                                    </rect>

                                    {/* OCR Text Overlay (Invisible but selectable/searchable) */}
                                    <text
                                        x={x1} y={y1 - (height * 0.15)} // Align bottom-right for RTL
                                        textAnchor="end"
                                        fontSize={fontSize}
                                        fill="transparent"
                                        stroke="none"
                                        className="pointer-events-none select-none" // For now, keep it simple. If we want selectable text, we need more complex logic.
                                        // "select-none" because native selection on SVG text is tricky with zoom/pan.
                                        // The user interacts via the list or clicking the box.
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

                        {/* Dimming Overlay with Hole */}
                        {activeLine !== null && (
                            <rect
                                x="0" y="0" width="100%" height="100%"
                                fill="rgba(0,0,0,0.3)"
                                mask="url(#highlightMask)"
                                className="pointer-events-none"
                            />
                        )}

                        {/* Active Line Stroke */}
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
                                        stroke="#3b82f6" // blue-500
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
            </div>
        </div>
    );
}
