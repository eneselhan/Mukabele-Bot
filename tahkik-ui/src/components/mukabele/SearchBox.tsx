"use client";

import React from "react";
import { useMukabele } from "./MukabeleContext";
import { Search, ChevronUp, ChevronDown, X } from "lucide-react";

export default function SearchBox() {
    const {
        searchQuery, setSearchQuery,
        searchMatches, currentSearchIndex,
        nextSearch, prevSearch
    } = useMukabele();

    return (
        <div className="p-3 bg-white border-b border-slate-200 sticky top-0 z-10 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Dizgide ara..."
                        className="w-full pl-9 pr-8 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery("")}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                        >
                            <X size={14} />
                        </button>
                    )}
                </div>
            </div>

            {searchQuery && (
                <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>
                        {searchMatches.length > 0
                            ? `${currentSearchIndex + 1} / ${searchMatches.length} eşleşme`
                            : "Sonuç yok"}
                    </span>
                    <div className="flex gap-1">
                        <button
                            onClick={prevSearch}
                            disabled={!searchMatches.length}
                            className="p-1 hover:bg-slate-100 rounded disabled:opacity-50"
                        >
                            <ChevronUp size={16} />
                        </button>
                        <button
                            onClick={nextSearch}
                            disabled={!searchMatches.length}
                            className="p-1 hover:bg-slate-100 rounded disabled:opacity-50"
                        >
                            <ChevronDown size={16} />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
