"use client";

import React, { useEffect } from "react";
import { useMukabele } from "./MukabeleContext";
import { useParams } from "next/navigation";
import SplitPane from "./SplitPane";
import LineList from "./LineList";
import PageCanvas from "./PageCanvas";
import ControlBar from "./ControlBar";
import ErrorNavigationPanel from "./ErrorNavigationPanel";
import ErrorDetailModal from "./ErrorDetailModal";

export default function MukabeleView() {
    const { isLoading, errorPopupData, setErrorPopupData } = useMukabele();
    // Data loading is now handled in MukabeleContext

    if (isLoading) {
        return (
            <div className="h-screen flex items-center justify-center bg-slate-50 text-slate-500 animate-pulse">
                Proje verileri hazırlanıyor...
            </div>
        );
    }

    return (
        <div className="flex flex-col h-screen overflow-hidden bg-slate-50 font-sans text-slate-900">
            <ControlBar />

            <div className="flex-1 overflow-hidden relative">
                <SplitPane
                    left={<div className="h-full w-full bg-white"><LineList /></div>}
                    right={<div className="h-full w-full bg-slate-100 relative"><PageCanvas /></div>}
                />
            </div>

            {/* Error Navigation Panel */}
            <ErrorNavigationPanel />

            {/* Error Detail Modal */}
            <ErrorDetailModal
                isOpen={!!errorPopupData}
                onClose={() => setErrorPopupData(null)}
                errorMeta={errorPopupData}
            />
        </div>
    );
}
