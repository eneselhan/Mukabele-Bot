"use client";

import React, { useState, useEffect, useRef } from "react";
import { useMukabele } from "./MukabeleContext";

export default function SplitPane({
    left,
    right
}: {
    left: React.ReactNode;
    right: React.ReactNode;
}) {
    const { splitRatio, setSplitRatio } = useMukabele();
    const containerRef = useRef<HTMLDivElement>(null);
    const [isDragging, setIsDragging] = useState(false);

    const handleMouseDown = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsDragging(true);
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
    };

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDragging || !containerRef.current) return;

            const req = containerRef.current.getBoundingClientRect();
            const x = e.clientX - req.left; // relative x
            const ratio = x / req.width;
            setSplitRatio(ratio);
        };

        const handleMouseUp = () => {
            if (isDragging) {
                setIsDragging(false);
                document.body.style.cursor = "";
                document.body.style.userSelect = "";
            }
        };

        if (isDragging) {
            window.addEventListener("mousemove", handleMouseMove);
            window.addEventListener("mouseup", handleMouseUp);
        }

        return () => {
            window.removeEventListener("mousemove", handleMouseMove);
            window.removeEventListener("mouseup", handleMouseUp);
        };
    }, [isDragging, setSplitRatio]);

    // Convert ratio to % for CSS
    // Subtract half of splitter width (e.g. 5px of 10px) to keep centering correct-ish
    const leftWidth = `calc(${splitRatio * 100}% - 5px)`;
    const rightWidth = `calc(${(1 - splitRatio) * 100}% - 5px)`;

    return (
        <div ref={containerRef} className="flex flex-row h-full w-full overflow-hidden relative">
            <div style={{ width: leftWidth }} className="h-full overflow-hidden">
                {left}
            </div>

            {/* Splitter Handle */}
            <div
                className="w-[10px] h-full cursor-col-resize bg-slate-100 hover:bg-slate-200 border-l border-r border-slate-200 transition-colors z-10 flex items-center justify-center"
                onMouseDown={handleMouseDown}
            >
                <div className="w-[2px] h-8 bg-slate-300 rounded-full" />
            </div>

            <div style={{ width: rightWidth }} className="h-full overflow-hidden">
                {right}
            </div>
        </div>
    );
}
