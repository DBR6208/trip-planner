import { useEffect, useRef, useState } from "react";

interface Props {
  pdfUrl: string;
  /** Called when user wants to go back to the markdown editor */
  onBack?: () => void;
  /** Called when user wants to download the PDF */
  onDownload?: () => void;
}

export default function PDFPreview({ pdfUrl, onBack, onDownload }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [numPages, setNumPages] = useState(0);
  const [pageNum, setPageNum] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const pdfDocRef = useRef<any>(null);
  const renderTaskRef = useRef<any>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadPDF() {
      setLoading(true);
      setError("");
      try {
        const pdfjsLib = await import("pdfjs-dist");
        // Set worker path to CDN (bundled worker is large; use CDN)
        pdfjsLib.GlobalWorkerOptions.workerSrc =
          "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/6.3.289/pdf.worker.min.mjs";

        const pdf = await pdfjsLib.getDocument({ url: pdfUrl }).promise;
        if (cancelled) return;

        pdfDocRef.current = pdf;
        setNumPages(pdf.numPages);
        setPageNum(1);
        setLoading(false);
        renderPage(pdf, 1);
      } catch (e: any) {
        if (cancelled) return;
        setError(e.message || "Failed to load PDF preview");
        setLoading(false);
      }
    }

    loadPDF();
    return () => { cancelled = true; };
  }, [pdfUrl]);

  function renderPage(pdf: any, num: number) {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Cancel any in-progress render
    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
    }

    // Get container width for responsive sizing
    const container = containerRef.current;
    const desiredWidth = container ? Math.min(container.clientWidth - 32, 800) : 800;

    pdf.getPage(num).then((page: any) => {
      const viewport = page.getViewport({ scale: 1 });
      const scale = desiredWidth / viewport.width;
      const scaledViewport = page.getViewport({ scale });

      canvas.width = scaledViewport.width;
      canvas.height = scaledViewport.height;

      const ctx = canvas.getContext("2d")!;
      const renderTask = page.render({
        canvasContext: ctx,
        viewport: scaledViewport,
      });
      renderTaskRef.current = renderTask;
      return renderTask.promise;
    });
  }

  function goToPage(n: number) {
    if (!pdfDocRef.current || n < 1 || n > numPages) return;
    setPageNum(n);
    renderPage(pdfDocRef.current, n);
  }

  return (
    <div className="panel p-4">
      {/* Header with controls */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-brand-blue flex items-center gap-1.5">
          Brochure Preview
        </h2>
        <div className="flex items-center gap-2">
          {onBack && (
            <button onClick={onBack} className="btn btn-ghost btn-xs gap-1">
              Back to Edit
            </button>
          )}
          {onDownload && (
            <button onClick={onDownload} className="btn btn-primary btn-xs gap-1">
              Download PDF
            </button>
          )}
        </div>
      </div>

      {/* PDF canvas */}
      <div ref={containerRef} className="bg-gray-100 rounded-lg overflow-hidden flex justify-center">
        {loading && (
          <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
            Loading preview…
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center py-16 text-red-500 text-sm">
            {error}
          </div>
        )}
        <canvas
          ref={canvasRef}
          className={loading || error ? "hidden" : "block shadow-md"}
          style={{ maxWidth: "100%" }}
        />
      </div>

      {/* Page nav */}
      {numPages > 1 && !loading && !error && (
        <div className="flex items-center justify-center gap-3 mt-3 text-xs text-gray-500">
          <button
            onClick={() => goToPage(pageNum - 1)}
            disabled={pageNum <= 1}
            className="btn btn-xs btn-ghost disabled:opacity-30"
          >
            Prev
          </button>
          <span>
            Page {pageNum} of {numPages}
          </span>
          <button
            onClick={() => goToPage(pageNum + 1)}
            disabled={pageNum >= numPages}
            className="btn btn-xs btn-ghost disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}