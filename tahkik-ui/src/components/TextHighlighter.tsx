import React from 'react';

// Types for Highlight objects
export interface TextHighlight {
    start: number;
    end: number;
    color: string;
    type?: string;
    metadata?: {
        wrong?: string;
        suggestion?: string;
        reason?: string;
        sources?: string[];
    };
}

interface TextHighlighterProps {
    text: string;
    highlights: TextHighlight[];
    className?: string;
    onHighlightClick?: (h: TextHighlight) => void;
}

const COLOR_MAP: Record<string, string> = {
    red: "bg-red-200 hover:bg-red-300 border-b-2 border-red-400 cursor-pointer",
    orange: "bg-orange-200 hover:bg-orange-300 border-b-2 border-orange-400 cursor-pointer",
    green: "bg-green-200 hover:bg-green-300 border-b-2 border-green-400 cursor-pointer",
    yellow: "bg-yellow-200 hover:bg-yellow-300 border-b-2 border-yellow-400 cursor-pointer",
    default: "bg-gray-200 hover:bg-gray-300 border-b-2 border-gray-400 cursor-pointer"
};

const TextHighlighter: React.FC<TextHighlighterProps> = ({ text, highlights, className = "", onHighlightClick }) => {
    if (!text) return null;
    if (!highlights || highlights.length === 0) {
        return <span className={className}>{text}</span>;
    }

    // Sort highlights by start index to process sequentially
    // Filter out invalid ranges
    const sorted = [...highlights]
        .filter(h => h.start >= 0 && h.end <= text.length && h.start < h.end)
        .sort((a, b) => a.start - b.start);

    const parts: React.ReactNode[] = [];
    let lastIndex = 0;

    sorted.forEach((h, idx) => {
        // 1. Plain text before this highlight
        if (h.start > lastIndex) {
            parts.push(
                <span key={`plain-${idx}`}>
                    {text.slice(lastIndex, h.start)}
                </span>
            );
        }

        // 2. The Highlighted Segment
        const segment = text.slice(h.start, h.end);
        const colorClass = COLOR_MAP[h.color] || COLOR_MAP.default;

        parts.push(
            <span
                key={`high-${idx}`}
                className={`${colorClass} rounded px-0.5 mx-0.5 transition-colors`}
                title={h.metadata?.reason || h.metadata?.suggestion || "İmla Hatası"}
                onClick={(e) => {
                    e.stopPropagation();
                    onHighlightClick && onHighlightClick(h);
                }}
            >
                {segment}
            </span>
        );

        lastIndex = h.end;
    });

    // 3. Remaining text
    if (lastIndex < text.length) {
        parts.push(
            <span key="plain-end">
                {text.slice(lastIndex)}
            </span>
        );
    }

    return (
        <div className={`leading-loose text-lg font-arabic ${className} rtl`} dir="rtl">
            {parts}
        </div>
    );
};

export default TextHighlighter;
