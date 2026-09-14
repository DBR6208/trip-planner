import { PDFViewer, ScrollStrategy } from "@embedpdf/react-pdf-viewer";

interface Props {
  pdfUrl: string;
  /** Called when user wants to go back to the markdown editor */
  onBack?: () => void;
  /** Called when user wants to download the PDF */
  onDownload?: () => void;
}

export default function PDFPreview({ pdfUrl, onBack, onDownload }: Props) {
  return (
    <div className="panel p-4 h-full min-h-0 flex flex-col">
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
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

      <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-gray-200 bg-white">
        <PDFViewer
          config={{
            src: pdfUrl,
            theme: { preference: "light" },
            tabBar: "never",
            disabledCategories: ["annotation", "redaction", "insert"],
            zoom: {
              defaultZoomLevel: 1,
            },
            scroll: {
              defaultStrategy: ScrollStrategy.Horizontal,
            },
          }}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
}