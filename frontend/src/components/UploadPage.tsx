"use client";

import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { analyzeStatement } from "@/lib/api";

type Stage = "idle" | "uploading" | "done";

const ACCEPTED = ".pdf,.csv,.xlsx,.xls";
const BANKS = ["HDFC", "ICICI", "SBI", "Axis"];

export function UploadPage() {
  const [stage, setStage] = useState<Stage>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [downloadName, setDownloadName] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    setStage("idle");
    setFile(null);
    setDownloadUrl(null);
    setDownloadName("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleFile = useCallback((f: File) => {
    setFile(f);
    setStage("idle");
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    setDownloadUrl(null);
  }, [downloadUrl]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const analyze = async () => {
    if (!file) return;
    setStage("uploading");
    try {
      const blob = await analyzeStatement(file);
      const url = URL.createObjectURL(blob);
      const name = file.name.replace(/\.[^.]+$/, "") + "_categorized.xlsx";
      setDownloadUrl(url);
      setDownloadName(name);
      setStage("done");
      toast.success("Done! Your categorized Excel is ready.");
    } catch (err: unknown) {
      setStage("idle");
      toast.error(err instanceof Error ? err.message : "Analysis failed.");
    }
  };

  return (
    <div className="min-h-screen bg-[#0f1117] flex flex-col items-center justify-center px-4 py-12">

      {/* Logo + title */}
      <div className="flex items-center gap-2.5 mb-2">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
          <svg className="w-4.5 h-4.5 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M3 13.5V19a1 1 0 001 1h4a1 1 0 001-1v-3.5M3 13.5V9m0 4.5h6M9 19V9m0 0V5a1 1 0 011-1h4a1 1 0 011 1v4M9 9h6m0 0v10a1 1 0 001 1h4a1 1 0 001-1V9m-6 0h6" />
          </svg>
        </div>
        <span className="text-white font-semibold text-xl tracking-tight">Expense Intelligence</span>
      </div>
      <p className="text-slate-500 text-sm mb-8">
        Upload a credit card statement · get a categorized Excel instantly
      </p>

      {/* Main card */}
      <div className="w-full max-w-md bg-[#16181f] border border-white/[0.07] rounded-2xl overflow-hidden shadow-xl">

        {/* Drop zone */}
        <div
          onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          onClick={() => stage !== "uploading" && inputRef.current?.click()}
          className={`
            m-4 rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2.5
            transition-all duration-150 select-none
            ${stage === "uploading" ? "py-10 border-slate-700 cursor-default" :
              isDragging ? "py-10 border-blue-500 bg-blue-500/5 cursor-copy" :
              file ? "py-8 border-slate-600 hover:border-slate-500 cursor-pointer" :
              "py-10 border-slate-700 hover:border-slate-500 cursor-pointer"}
          `}
        >
          <input ref={inputRef} type="file" accept={ACCEPTED} className="hidden" onChange={onInputChange} />

          {stage === "uploading" ? (
            <>
              <div className="relative w-10 h-10">
                <svg className="w-10 h-10 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-10" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                  <path className="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
              <p className="text-slate-300 text-sm font-medium">Analyzing with AI…</p>
              <p className="text-slate-600 text-xs">Parsing transactions and categorizing</p>
            </>
          ) : file ? (
            <>
              <div className="w-9 h-9 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                <svg className="w-4.5 h-4.5 text-emerald-400" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div className="text-center">
                <p className="text-slate-200 text-sm font-medium leading-snug max-w-[260px] truncate">{file.name}</p>
                <p className="text-slate-600 text-xs mt-0.5">{(file.size / 1024).toFixed(0)} KB · click to change</p>
              </div>
            </>
          ) : (
            <>
              <div className="w-9 h-9 rounded-full bg-slate-800 flex items-center justify-center">
                <svg className="w-4.5 h-4.5 text-slate-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div className="text-center">
                <p className="text-slate-300 text-sm font-medium">Drop your statement here</p>
                <p className="text-slate-600 text-xs mt-0.5">PDF, CSV or Excel · max 50 MB</p>
              </div>
            </>
          )}
        </div>

        {/* Supported banks */}
        <div className="px-4 pb-4 flex items-center gap-1.5">
          <span className="text-slate-600 text-xs mr-0.5">Supports</span>
          {BANKS.map(b => (
            <span key={b} className="text-xs text-slate-400 bg-white/[0.04] border border-white/[0.06] px-2 py-0.5 rounded-md">
              {b}
            </span>
          ))}
        </div>

        {/* Divider */}
        <div className="h-px bg-white/[0.05] mx-4" />

        {/* Action area */}
        <div className="p-4 flex flex-col gap-2">
          {stage !== "done" ? (
            <button
              onClick={analyze}
              disabled={!file || stage === "uploading"}
              className="w-full h-10 rounded-lg text-sm font-semibold bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              {stage === "uploading" ? "Analyzing…" : "Analyze & Download Excel"}
            </button>
          ) : (
            <>
              <a
                href={downloadUrl!}
                download={downloadName}
                className="w-full h-10 rounded-lg text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download Excel
              </a>
              <button
                onClick={reset}
                className="w-full h-9 rounded-lg text-xs text-slate-500 hover:text-slate-300 transition-colors"
              >
                Analyze another file
              </button>
            </>
          )}
        </div>
      </div>

      <p className="mt-5 text-slate-700 text-xs">Processed locally · never stored</p>
    </div>
  );
}
