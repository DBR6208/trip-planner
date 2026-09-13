import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const markdownComponents = {
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

interface Props {
  markdown: string;
}

export default function HtmlPreview({ markdown }: Props) {
  return (
    <div className="panel p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-brand-blue">
          Live HTML Preview
        </h2>
        <span className="text-[11px] uppercase tracking-widest text-gray-400">
          Rendered markdown
        </span>
      </div>

      <div className="flex-1 min-h-[560px] scroll-content pr-1">
        {markdown?.trim() ? (
          <div className="markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {markdown}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-sm text-gray-400 text-center px-6">
            Generate the brochure or edit the markdown to see the HTML preview here.
          </div>
        )}
      </div>
    </div>
  );
}
