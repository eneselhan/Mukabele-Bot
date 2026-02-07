"use client";
import { useEffect, useState } from "react";
import { Save, Play } from "lucide-react";

// Gelen verinin tam şeması
interface BestMatch {
  raw: string; // Hizalanmış asıl metin
  score: number;
}

interface LineData {
  line_no: number;
  line_image: string; // "C:\Users...\page_0001_line_001.png"
  ocr_text: string;   // Ham OCR çıktısı
  best?: BestMatch;   // Hizalanmış metin (Varsa)
}

export default function EditorPage() {
  const [data, setData] = useState<LineData[]>([]);
  const [loading, setLoading] = useState(true);

  // 1. Veriyi Çek, 'aligned' kutusunu bul ve SIRALA
  useEffect(() => {
    fetch("http://localhost:8000/output_lines/alignment.json")
      .then((res) => {
        if (!res.ok) throw new Error("Dosya bulunamadı");
        return res.json();
      })
      .then((jsonData) => {
        console.log("JSON Yüklendi:", jsonData);

        // HEDEF: "aligned" dizisini bulmak
        let listToUse: LineData[] = [];

        if (jsonData.aligned && Array.isArray(jsonData.aligned)) {
          listToUse = jsonData.aligned;
        } else if (Array.isArray(jsonData)) {
          listToUse = jsonData;
        }
        // Sıralama (line_no alanına göre garanti sıralama)
        const sortedData = listToUse.sort((a, b) => (a.line_no || 0) - (b.line_no || 0));

        setData(sortedData);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Veri Hatası:", err);
        setLoading(false);
      });
  }, []);

  // 2. Resim Yolunu Temizleme Fonksiyonu
  const getImageUrl = (fullPath: string) => {
    if (!fullPath) return "/placeholder.png";
    // Windows yolundan dosya ismini al (son parça)
    const filename = fullPath.split(/[/\\]/).pop();
    // Backend'den iste
    return `http://localhost:8000/output_lines/lines/${filename}`;
  };

  if (loading) return <div className="p-10 text-center">Editör Hazırlanıyor...</div>;

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      {/* Liste */}
      <div className="space-y-6 max-w-5xl mx-auto pb-20">
        {data.map((item, index) => (
          <div key={index} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col gap-4 p-4 mb-4">

            {/* Üst Kısım: Resim ve Bilgiler */}
            <div className="flex justify-between items-start border-b pb-2">
              <span className="font-bold text-gray-700">Satır #{item.line_no}</span>
              <span className="text-xs text-gray-400">{item.line_image.split(/[/\\]/).pop()}</span>
            </div>
            <div className="flex flex-col md:flex-row gap-4">

              {/* 1. RESİM */}
              <div className="w-full md:w-1/3 border border-gray-300 bg-gray-50 rounded p-2 flex items-center justify-center">
                <img
                  src={getImageUrl(item.line_image)}
                  alt={`Satır ${index + 1}`}
                  className="max-h-32 object-contain"
                  crossOrigin="anonymous"
                />
              </div>
              {/* 2. OCR METNİ (Referans için - Sadece Okunur) */}
              <div className="flex-1">
                <label className="text-xs font-bold text-red-500 block mb-1">OCR (Resimden Okunan):</label>
                <div className="p-2 bg-red-50 border border-red-200 rounded text-right text-sm text-gray-700 font-arabic leading-loose h-full">
                  {item.ocr_text || "OCR Okuyamadı"}
                </div>
              </div>
              {/* 3. EŞLEŞEN METİN (Word'den Gelen - Düzenlenebilir) */}
              <div className="flex-1">
                <label className="text-xs font-bold text-blue-600 block mb-1">Hizalanmış (Word'den):</label>
                <textarea
                  className="w-full h-full p-2 border-2 border-blue-100 rounded focus:border-blue-500 outline-none text-right text-lg font-arabic leading-loose"
                  defaultValue={item.best?.raw || ""}
                  dir="rtl"
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
