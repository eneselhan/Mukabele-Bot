"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, BookOpen } from "lucide-react";

export default function MukabelePage() {
    const params = useParams();
    const router = useRouter();
    const [data, setData] = useState<any>(null);
    const [currentIndex, setCurrentIndex] = useState(0);

    useEffect(() => {
        fetch(`http://localhost:8000/api/projects/${params.id}/mukabele-data`)
            .then(res => res.json())
            .then(res => setData(res));
    }, [params.id]);

    if (!data) return <div className="p-10 text-center">Mukabele Verileri Yükleniyor...</div>;

    const currentSegment = data?.segments?.[currentIndex] || null;

    if (!currentSegment) {
        return (
            <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-10 text-center">
                <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 max-w-md">
                    <h2 className="text-xl font-bold text-slate-800 mb-2">Henüz Analiz Verisi Yok</h2>
                    <p className="text-slate-500 mb-6">
                        Bu proje için henüz bir analiz işlemi tamamlanmamış veya sonuçlar oluşturulmamış.
                    </p>
                    <button
                        onClick={() => router.back()}
                        className="bg-blue-600 text-white px-6 py-2 rounded-lg font-bold"
                    >
                        Geri Dön ve Analiz Başlat
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
            {/* ÜST BAR */}
            <div className="bg-white border-b p-4 flex justify-between items-center shadow-sm">
                <button onClick={() => router.back()} className="text-slate-500 hover:text-slate-800 flex items-center gap-2 transition-colors">
                    <ArrowLeft size={16} /> Geri Dön
                </button>
                <h1 className="font-bold text-lg flex items-center gap-2 text-slate-800">
                    <BookOpen className="text-blue-600" /> Mukabele Ekranı
                </h1>
                <div className="w-20"></div> {/* Spacer */}
            </div>

            {/* İÇERİK */}
            <div className="flex-1 p-6 grid grid-cols-1 md:grid-cols-2 gap-8 max-w-7xl mx-auto w-full items-center">

                {/* SOL: REFERANS METİN */}
                <div className="bg-white p-8 rounded-xl shadow-lg border border-slate-200 flex flex-col justify-center items-center text-center h-[500px]">
                    <h3 className="text-sm font-bold text-slate-400 mb-6 uppercase tracking-wider border-b pb-2 w-full">Referans Metin (Word)</h3>
                    <div className="flex-1 flex items-center justify-center">
                        <p className="text-2xl font-serif text-slate-800 leading-relaxed dir-rtl">
                            {currentSegment.ref_text}
                        </p>
                    </div>
                </div>

                {/* SAĞ: NÜSHA GÖRÜNTÜSÜ */}
                <div className="bg-slate-800 p-8 rounded-xl shadow-lg flex flex-col justify-center items-center text-center relative overflow-hidden h-[500px] border border-slate-700">
                    <h3 className="text-sm font-bold text-slate-400 mb-6 uppercase tracking-wider border-b border-slate-700 pb-2 w-full">Nüsha #1 (OCR)</h3>

                    <div className="flex-1 w-full flex flex-col items-center justify-center gap-6">
                        {/* Placeholder Resim Alanı */}
                        <div className="w-full h-40 bg-black/40 rounded-lg border border-slate-600 flex items-center justify-center text-slate-500 text-sm font-mono shadow-inner">
                            [Satır Görüntüsü Burada Olacak]
                            <br />
                            {currentSegment.nushas["1"]?.img_url}
                        </div>

                        <p className="text-xl font-mono text-green-400 bg-slate-900/50 p-4 rounded-lg w-full border border-slate-700/50">
                            {currentSegment.nushas["1"]?.text}
                        </p>
                    </div>
                </div>
            </div>

            {/* ALT BAR: NAVİGASYON */}
            <div className="bg-white border-t p-4 flex justify-center gap-4 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] fixed bottom-0 w-full z-10">
                <button
                    disabled={currentIndex === 0}
                    onClick={() => setCurrentIndex(i => i - 1)}
                    className="px-6 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-bold disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors border border-slate-200"
                >
                    <ArrowLeft size={18} /> Önceki Satır
                </button>

                <div className="px-6 py-3 font-mono text-slate-600 font-bold bg-slate-50 rounded-lg border border-slate-200 min-w-[120px] text-center">
                    {currentIndex + 1} / {data.segments.length}
                </div>

                <button
                    disabled={currentIndex === data.segments.length - 1}
                    onClick={() => setCurrentIndex(i => i + 1)}
                    className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors shadow-md shadow-blue-200"
                >
                    Sonraki Satır <ArrowRight size={18} />
                </button>
            </div>

            {/* Spacer for fixed bottom bar */}
            <div className="h-24"></div>
        </div>
    );
}
