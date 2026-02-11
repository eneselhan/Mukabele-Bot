
export function escapeHtml(s: string) {
    return (s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

export function classifyErr(meta: any) {
    const src = meta.sources || [];
    if (!src || src.length === 0) return "bg-red-200"; // err-both err-unknown
    const hasG = src.includes("gemini");
    const hasO = src.includes("openai");
    const hasC = src.includes("claude");

    if (hasG && hasO && hasC) return "bg-green-200"; // err-all (all 3 agree)
    if (hasG && hasO) return "bg-[#C49A6C]"; // err-gptgem (GPT+Gemini)
    if (hasO && hasC) return "bg-[#CD7F32]"; // err-gptclaude (GPT+Claude)
    if (hasG && hasC) return "bg-red-200"; // err-both

    if (hasG) return "bg-orange-200"; // err-gem
    if (hasO) return "bg-blue-200";   // err-oa
    if (hasC) return "bg-purple-200"; // err-claude

    return "bg-red-200";
}

export function tooltipText(meta: any) {
    const s = [];
    if (meta.suggestion) s.push("Öneri: " + meta.suggestion);
    if (meta.reason) s.push("Not: " + meta.reason);
    const src = (meta.sources || []).join(", ");
    if (src) s.push("Kaynak: " + src);
    return s.join("\n");
}

// Update signature
export function highlightTextArabic(raw: string, startWord: number, lineMarks: any[], activeWordIndex: number | null = null) {
    if (!raw) return "";

    // Map by global token index
    const byIdx: { [key: number]: any } = {};
    if (lineMarks && lineMarks.length > 0) {
        lineMarks.forEach(m => {
            const gi = m.gidx;
            if (typeof gi === "number") byIdx[gi] = m;
        });
    }

    // Split by whitespace but keep delimiters to reconstruct
    // Regex matches whitespace sequences
    const parts = raw.split(/(\s+)/);
    let tokI = 0;

    return parts.map(p => {
        if (!p) return "";
        if (/^\s+$/.test(p)) return escapeHtml(p); // Return whitespace as-is properly escaped

        const gidx = (typeof startWord === "number" ? startWord : 0) + tokI;
        tokI += 1;

        let cls = "";
        let tip = "";
        let metaJson = "";

        // Spellcheck
        if (byIdx[gidx]) {
            const meta = byIdx[gidx];
            cls = classifyErr(meta);
            tip = tooltipText(meta);
            metaJson = JSON.stringify(meta).replace(/"/g, "&quot;");
        }

        // TTS Active Word
        if (activeWordIndex !== null && gidx === activeWordIndex) {
            // Apply distinct style (e.g. bright yellow background + bold)
            // If it already nas error class, append
            cls = (cls ? cls + " " : "") + "bg-yellow-300 font-bold ring-2 ring-yellow-400 z-10 relative";
        }

        if (cls || metaJson) {
            const titleAttr = tip ? ` title="${escapeHtml(tip)}"` : "";
            const dataAttr = metaJson ? ` data-meta="${metaJson}"` : "";
            const cursor = metaJson ? "cursor-help" : "";
            return `<span class="px-0.5 rounded ${cursor} ${cls}"${titleAttr}${dataAttr}>${escapeHtml(p)}</span>`;
        }

        return escapeHtml(p);
    }).join("");
}
