"use client";

import React, { createContext, useContext, useState, useRef, useEffect, useCallback } from "react";
import { useMukabele } from "./MukabeleContext"; // Assumes located in same folder

interface TTSContextType {
    isPlaying: boolean;
    isLoading: boolean;
    play: () => void;
    pause: () => void;
    stop: () => void;
    activeWordIndex: number | null; // Global token index for highlighting
    rate: number;
    setRate: (rate: number) => void;
    currentAudioChunk: number;
    totalAudioChunks: number;
    currentTime: number;
    duration: number;
    seek: (time: number) => void;
}

const TTSContext = createContext<TTSContextType | undefined>(undefined);

export function TTSProvider({ children }: { children: React.ReactNode }) {
    const { lines, pages, activePageKey, projectId, nushaIndex } = useMukabele() as any; // Need access to lines text

    const [isPlaying, setIsPlaying] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [activeWordIndex, setActiveWordIndex] = useState<number | null>(null);
    const [rate, setRateState] = useState(1.0);
    const [currentAudioChunk, setCurrentAudioChunk] = useState(0);
    const [totalAudioChunks, setTotalAudioChunks] = useState(0);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);

    // Audio State
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const chunksRef = useRef<any[]>([]); // { audio_url, timepoints, start_token }
    const chunkIndexRef = useRef(0);
    const timepointsRef = useRef<any[]>([]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (audioRef.current) {
                audioRef.current.pause();
                audioRef.current = null;
            }
        };
    }, []);



    const setRate = (r: number) => {
        setRateState(r);
        if (audioRef.current) {
            audioRef.current.playbackRate = r;
        }
    };

    const fetchAudio = async () => {
        // Gather text from current visible lines
        if (!lines || lines.length === 0) return;

        // Collect tokens and map them to global indices
        // Ideally we should do this page by page or the whole document
        // For simplicity, let's vocalize the *active page* or *lines currently in view*?
        // Let's grab all lines for now (might be heavy for huge docs, but okay for typical manuscript pages)

        // Filter for Active Page Lines ONLY
        // Filter for Active Page Lines ONLY
        if (!activePageKey || !pages.length) {
            console.warn("[TTS] No active page or pages loaded.");
            alert("Etkin sayfa bulunamadı. Lütfen sayfayı yenileyiniz.");
            return;
        }
        const activePage = pages.find((p: any) => p.key === activePageKey);
        if (!activePage) {
            console.warn("[TTS] Active page not found in pages list.");
            alert("Etkin sayfa verisi bulunamadı.");
            return;
        }
        const targetLines = activePage.lines || [];

        const allTokens: string[] = [];
        targetLines.forEach((l: any) => {
            const raw = l.best?.raw || "";
            if (raw) {
                allTokens.push(...raw.split(/\s+/));
            }
        });

        if (allTokens.length === 0) {
            console.warn("[TTS] No tokens found.");
            alert("Seslendirilecek metin bulunamadı (Sayfa boş veya yüklenemedi).");
            return;
        }
        console.log("[TTS] Fetching for tokens:", allTokens.length);

        setIsLoading(true);
        try {
            // Check if backend has cached audio or generate on fly
            // We'll send tokens to /api/tts
            const res = await fetch("http://127.0.0.1:8000/api/tts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    tokens: allTokens,
                    speaking_rate: rate,
                    nusha_id: nushaIndex || 1,
                    page_key: activePageKey || "page_unknown",
                    archive_path: projectId // Use project ID as archive path for caching
                })
            });
            const data = await res.json();

            if (data.chunks) {
                // Process chunks
                let globalTokenOffset = 0;
                const processedChunks = data.chunks.map((c: any) => {
                    // Create blob URL for audio
                    const byteCharacters = atob(c.audio_b64);
                    const byteNumbers = new Array(byteCharacters.length);
                    for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                    }
                    const byteArray = new Uint8Array(byteNumbers);
                    const blob = new Blob([byteArray], { type: "audio/mp3" });
                    const url = URL.createObjectURL(blob);

                    const chunkInfo = {
                        url,
                        timepoints: c.timepoints,
                        start_token: globalTokenOffset
                    };

                    // Estimate token count in this chunk to update offset?
                    // Actually the backend might not return token counts per chunk easily 
                    // unless we parse timepoints.
                    // But wait, our backend splits by sentence ~300 chars.
                    // We assumed linear progression.
                    // ISSUE: Synchronization depends on accurate token mapping.
                    // The backend `process_tts_request` generates timepoints with mark names like "w123".
                    // "w{real_idx}" where real_idx is global index. PERFECT!

                    return chunkInfo;
                });

                chunksRef.current = processedChunks;
                setTotalAudioChunks(processedChunks.length);
                setCurrentAudioChunk(0);
                chunkIndexRef.current = 0;

                // Start playing first chunk
                playChunk(0);
            }
        } catch (e) {
            console.error("TTS Fetch Error", e);
            alert("Ses verisi alınamadı via API.");
        } finally {
            setIsLoading(false);
        }
    };

    const playChunk = (index: number) => {
        if (index >= chunksRef.current.length) {
            stop();
            return;
        }

        const chunk = chunksRef.current[index];
        setCurrentAudioChunk(index);
        chunkIndexRef.current = index;
        timepointsRef.current = chunk.timepoints || [];

        if (audioRef.current) {
            audioRef.current.src = chunk.url;
            audioRef.current.playbackRate = rate;
            audioRef.current.play().catch(e => {
                console.error("Play error (Ref)", e);
                alert("Ses çalınamadı. Tarayıcı izinlerini kontrol ediniz.\nHata: " + e.message);
            });
            setIsPlaying(true);
        } else {
            console.log("[TTS] Creating new Audio object for chunk", index);
            const audio = new Audio(chunk.url);
            audio.playbackRate = rate;
            audio.onended = () => {
                console.log("[TTS] Chunk ended", index);
                playChunk(chunkIndexRef.current + 1);
            };
            audio.onerror = (e) => {
                console.error("Audio Load Error", e);
                alert("Ses dosyası yüklenemedi (Decoding Error).");
            };
            audio.ontimeupdate = handleTimeUpdate;
            audioRef.current = audio;
            audio.onloadedmetadata = handleLoadedMetadata;
            audio.play().catch(e => {
                console.error("Play error (New)", e);
                alert("Ses başlatılamadı (Autoplay Policy?).\nHata: " + e.message);
            });
            setIsPlaying(true);
        }
    };

    const handleLoadedMetadata = () => {
        if (audioRef.current) {
            setDuration(audioRef.current.duration);
        }
    };


    const handleTimeUpdate = () => {
        if (!audioRef.current) return;
        const t = audioRef.current.currentTime;
        setCurrentTime(t);

        // Find latest timepoint
        // Timepoints are like [{mark: "w5", time: 0.12}, ...]
        const tps = timepointsRef.current;
        for (let i = tps.length - 1; i >= 0; i--) {
            if (t >= tps[i].time) {
                const mark = tps[i].mark; // e.g., "w12"
                if (mark.startsWith("w")) {
                    const idx = parseInt(mark.substring(1));
                    setActiveWordIndex(idx);
                }
                break;
            }
        }
    };

    const play = useCallback(() => {
        console.log("[TTS] Play called. Lines:", lines?.length, "Chunks:", chunksRef.current.length);
        if (chunksRef.current.length > 0) {
            // Resume or restart
            if (audioRef.current) {
                console.log("[TTS] Resuming audioRef");
                audioRef.current.play();
                setIsPlaying(true);
            } else {
                console.log("[TTS] Playing chunk 0");
                playChunk(0);
            }
        } else {
            // Initial fetch and play
            console.log("[TTS] Fetching audio...");
            fetchAudio();
        }
    }, [lines, rate, activePageKey, pages, projectId, nushaIndex]); /* Added dependencies to avoid stale state */

    const pause = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            setIsPlaying(false);
        }
    }, []);

    const stop = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
        }
        setIsPlaying(false);
        setActiveWordIndex(null);
        // Retain chunks for replay? Or clear? 
        // Let's keep them.
        // Let's keep them.
    }, []);

    // Reset audio when page changes
    useEffect(() => {
        stop();
        chunksRef.current = [];
        setTotalAudioChunks(0);
        setCurrentAudioChunk(0);
    }, [activePageKey, stop]);

    const seek = (time: number) => {
        if (audioRef.current) {
            audioRef.current.currentTime = time;
            setCurrentTime(time);
        }
    };

    return (
        <TTSContext.Provider value={{
            isPlaying, isLoading, play, pause, stop,
            activeWordIndex, rate, setRate,
            currentAudioChunk, totalAudioChunks,
            currentTime, duration, seek
        }}>
            {children}
        </TTSContext.Provider>
    );
}

export function useTTS() {
    const context = useContext(TTSContext);
    if (context === undefined) {
        throw new Error("useTTS must be used within a TTSProvider");
    }
    return context;
}
