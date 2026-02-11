"use client";
import Link from "next/link";
import { BookOpen, ArrowRight, Layers, Eye, FileText, Sparkles, CheckCircle } from "lucide-react";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-purple-50/30">
      {/* Navbar */}
      <nav className="border-b border-slate-100 bg-white/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-6 py-3 flex justify-between items-center">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-purple-600 flex items-center justify-center text-white shadow-sm shadow-purple-200">
              <BookOpen size={16} />
            </div>
            <span className="text-base font-extrabold text-slate-800 tracking-tight">Tahkik Bot</span>
          </div>
          <Link
            href="/projects"
            className="text-sm font-bold text-purple-600 hover:text-purple-700 transition-colors"
          >
            Projelerim →
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-16 pb-12">
        <div className="text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-1.5 bg-purple-100 text-purple-700 px-3 py-1 rounded-full text-xs font-bold mb-5">
            <Sparkles size={12} />
            AI Destekli Yazma Analizi
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold text-slate-900 leading-tight tracking-tight">
            Yazma Eserleri İçin
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-indigo-600">
              Akıllı Mukabele Sistemi
            </span>
          </h1>
          <p className="text-slate-500 mt-5 text-base leading-relaxed max-w-lg mx-auto">
            PDF yazma eserlerinizi yükleyin, yapay zeka ile satır satır OCR yapın,
            referans metinle otomatik hizalayın ve nüshaları karşılaştırın.
          </p>

          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/projects"
              className="bg-purple-600 text-white px-6 py-3 rounded-xl hover:bg-purple-700 transition-all shadow-lg shadow-purple-200 flex items-center gap-2 text-sm font-bold group"
            >
              Mukabele Projesi Başlat
              <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="max-w-5xl mx-auto px-6 pb-16">
        <h2 className="text-center text-sm font-bold text-slate-400 uppercase tracking-widest mb-8">Nasıl Çalışır</h2>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            {
              icon: <FileText size={22} />,
              step: "1",
              title: "Dosya Yükleme",
              desc: "Yazma eseri PDF'lerini ve referans Word metnini yükleyin."
            },
            {
              icon: <Layers size={22} />,
              step: "2",
              title: "Segmentasyon",
              desc: "Sayfalar otomatik olarak satırlara ayrılır (Kraken AI)."
            },
            {
              icon: <Eye size={22} />,
              step: "3",
              title: "OCR & Hizalama",
              desc: "Google Vision ile metin tanıma ve referans metinle hizalama yapılır."
            },
            {
              icon: <CheckCircle size={22} />,
              step: "4",
              title: "Mukabele",
              desc: "Nüshaları yan yana karşılaştırın ve farkları inceleyin."
            }
          ].map((item) => (
            <div key={item.step} className="bg-white border border-slate-200 rounded-xl p-5 hover:shadow-md hover:border-purple-200 transition-all group">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-purple-100 text-purple-600 flex items-center justify-center group-hover:bg-purple-600 group-hover:text-white transition-colors">
                  {item.icon}
                </div>
                <span className="text-[11px] font-extrabold text-slate-300 uppercase">Adım {item.step}</span>
              </div>
              <h3 className="text-sm font-bold text-slate-800 mb-1">{item.title}</h3>
              <p className="text-xs text-slate-400 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features Grid */}
      <section className="max-w-5xl mx-auto px-6 pb-16">
        <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-8 text-white">
          <h2 className="text-lg font-bold mb-6">Öne Çıkan Özellikler</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {[
              { title: "Çoklu Nüsha Desteği", desc: "Birden fazla yazma nüshasını aynı projede yönetin." },
              { title: "Sürükle-Bırak Sıralama", desc: "Nüsha sıralamasını kolayca değiştirin." },
              { title: "Adım Adım Pipeline", desc: "Her analiz adımını bağımsız olarak başlatın." },
              { title: "Otomatik Hizalama", desc: "OCR çıktısını referans metinle DP algoritması ile hizalayın." },
              { title: "Satır Düzenleme", desc: "Mukabele ekranından metni doğrudan düzenleyin." },
              { title: "Toplu Yükleme", desc: "Birden fazla PDF'i aynı anda yükleyin." }
            ].map((f, i) => (
              <div key={i} className="bg-white/10 rounded-lg p-4 hover:bg-white/15 transition-colors">
                <h3 className="text-sm font-bold mb-1">{f.title}</h3>
                <p className="text-xs text-white/60 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="max-w-5xl mx-auto px-6 pb-12">
        <div className="text-center">
          <p className="text-sm text-slate-400 mb-3">Hemen başlayın</p>
          <Link
            href="/projects"
            className="inline-flex items-center gap-2 bg-purple-600 text-white px-5 py-2.5 rounded-xl hover:bg-purple-700 transition-all shadow-sm text-sm font-bold"
          >
            Projelerime Git
            <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-100 py-4 text-center text-[11px] text-slate-300">
        Tahkik Bot © 2025 — Yazma Eserleri Mukabele Sistemi
      </footer>
    </main>
  );
}
