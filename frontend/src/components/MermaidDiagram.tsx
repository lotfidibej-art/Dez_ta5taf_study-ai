"use client";

import React, { useEffect, useRef, useState, useId } from "react";
import mermaid from "mermaid";

interface MermaidDiagramProps {
  chart: string;
  className?: string;
}

export const MermaidDiagram: React.FC<MermaidDiagramProps> = ({ chart, className = "" }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>("");
  const [renderError, setRenderError] = useState<string | null>(null);
  const uniqueId = useId().replace(/:/g, "_");

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: "neutral",
      securityLevel: "loose",
      fontFamily: "ui-sans-serif, system-ui, sans-serif",
      flowchart: {
        htmlLabels: true,
        curve: "basis",
        nodeSpacing: 50,
        rankSpacing: 50,
      },
    });
  }, []);

  useEffect(() => {
    let isCancelled = false;

    const renderChart = async () => {
      if (!chart || !chart.trim()) {
        setSvgContent("");
        setRenderError(null);
        return;
      }

      setRenderError(null);
      const renderId = `mermaid_${uniqueId}_${Date.now()}`;

      try {
        const { svg } = await mermaid.render(renderId, chart.trim());
        if (!isCancelled) {
          setSvgContent(svg);
        }
      } catch (err: unknown) {
        console.warn("Mermaid diagram rendering error:", err);
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : String(err);
          setRenderError(msg);
        }
      }
    };

    renderChart();

    return () => {
      isCancelled = true;
    };
  }, [chart, uniqueId]);

  if (renderError) {
    return (
      <div className={`p-4 rounded-xl border border-amber-500/30 bg-amber-500/5 text-amber-200 text-xs font-mono ${className}`}>
        <div className="flex items-center gap-2 mb-2 text-amber-400 font-semibold text-sm">
          <span>⚠️ Visual Render Fallback</span>
        </div>
        <p className="mb-2 text-neutral-400">Diagram parsing hit a syntax issue. Raw structural flow:</p>
        <pre className="p-3 bg-neutral-900 rounded-lg overflow-x-auto text-[11px] leading-relaxed border border-neutral-800 text-neutral-300">
          {chart}
        </pre>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`overflow-x-auto flex justify-center items-center p-4 bg-neutral-900/60 rounded-xl border border-neutral-800 transition-all ${className}`}
      dangerouslySetInnerHTML={{ __html: svgContent }}
    />
  );
};
