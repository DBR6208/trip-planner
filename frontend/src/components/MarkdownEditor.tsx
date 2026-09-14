import CodeMirror from "@uiw/react-codemirror";
import { markdown } from "@codemirror/lang-markdown";

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function MarkdownEditor({ value, onChange }: Props) {
  return (
    <div className="h-full rounded-xl overflow-hidden border border-gray-200 bg-white">
      <CodeMirror
        value={value}
        height="100%"
        extensions={[markdown()]}
        onChange={onChange}
        className="h-full"
      />
    </div>
  );
}