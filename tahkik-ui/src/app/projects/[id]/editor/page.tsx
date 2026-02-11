"use client";

import { useParams, redirect } from "next/navigation";

export default function EditorPage() {
    const params = useParams();
    const id = params.id as string;
    redirect(`/projects/${id}/mukabele`);
}
