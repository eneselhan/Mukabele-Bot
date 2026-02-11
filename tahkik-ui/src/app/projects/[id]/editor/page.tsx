"use client";

import React from "react";
import { MukabeleProvider } from "@/components/mukabele/MukabeleContext";
import { TTSProvider } from "@/components/mukabele/TTSContext"; // Correct path assumed
import MukabeleView from "@/components/mukabele/MukabeleView";
import Navbar from "@/components/Navbar";

export default function EditorPage() {
    return (
        <>
            <Navbar />
            <MukabeleProvider>
                <TTSProvider>
                    <MukabeleView />
                </TTSProvider>
            </MukabeleProvider>
        </>
    );
}
