"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import { Home, Play, BookOpen, ChevronRight } from "lucide-react";

export default function Navbar() {
    const params = useParams();
    const pathname = usePathname();
    const projectId = params.id as string | undefined;

    // Determine active page
    const isProcess = pathname?.includes("/process");
    const isEditor = pathname?.includes("/editor") || pathname?.includes("/mukabele");

    return (
        <nav className="bg-white border-b border-slate-200 shadow-sm">
            <div className="max-w-7xl mx-auto px-4 py-3">
                <div className="flex items-center justify-between">
                    {/* Left: Breadcrumb */}
                    <div className="flex items-center gap-2 text-sm">
                        <Link
                            href="/"
                            className="flex items-center gap-1.5 text-slate-600 hover:text-slate-900 transition-colors"
                        >
                            <Home size={16} />
                            <span className="font-medium">Ana Sayfa</span>
                        </Link>

                        {projectId && (
                            <>
                                <ChevronRight size={14} className="text-slate-400" />
                                <span className="text-slate-900 font-semibold">Proje</span>
                            </>
                        )}
                    </div>

                    {/* Right: Navigation Links */}
                    {projectId && (
                        <div className="flex items-center gap-1">
                            <Link
                                href={`/projects/${projectId}/process`}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${isProcess
                                    ? "bg-green-50 text-green-700"
                                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                                    }`}
                            >
                                <Play size={16} />
                                İşlem
                            </Link>

                            <Link
                                href={`/projects/${projectId}/editor`}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${isEditor
                                    ? "bg-purple-50 text-purple-700"
                                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                                    }`}
                            >
                                <BookOpen size={16} />
                                Mukabele
                            </Link>
                        </div>
                    )}
                </div>
            </div>
        </nav>
    );
}
