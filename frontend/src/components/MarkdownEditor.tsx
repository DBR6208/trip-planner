import CodeMirror from "@uiw/react-codemirror";
import { markdown } from "@codemirror/lang-markdown";
import { oneDark } from "@codemirror/theme-one-dark";

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function MarkdownEditor({ value, onChange }: Props) {
  return (
    <div className="rounded-xl overflow-hidden border border-gray-200 bg-[#0f172a] min-h-[560px]">
      <CodeMirror
        value={value}
        height="560px"
        theme={oneDark}
        extensions={[markdown()]}
        onChange={onChange}
      />
    </div>
  );
}
