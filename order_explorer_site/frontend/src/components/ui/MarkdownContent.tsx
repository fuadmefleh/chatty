import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { highlight, escapeHtml } from '../../lib/prismHighlight';

// react-markdown gives fenced code blocks a `language-xxx` className (from the
// fence's info string); inline code gets none. Map common shorthand aliases to
// the grammar names registered in lib/prismHighlight.
const LANGUAGE_ALIASES: Record<string, string> = {
  js: 'javascript',
  ts: 'typescript',
  py: 'python',
  sh: 'bash',
  shell: 'bash',
  yml: 'yaml',
  md: 'markdown',
  html: 'markup',
  htm: 'markup',
};

const CodeBlock: React.FC<{ className?: string; children?: React.ReactNode; streaming?: boolean }> = ({
  className,
  children,
  streaming,
}) => {
  const languageMatch = /language-(\w+)/.exec(className || '');
  const content = String(children ?? '').replace(/\n$/, '');

  const language = languageMatch ? languageMatch[1] : null;
  const resolvedLanguage = language ? LANGUAGE_ALIASES[language] || language : null;

  const highlighted = useMemo(() => {
    if (!resolvedLanguage || streaming) return null;
    return highlight(content, resolvedLanguage);
  }, [content, resolvedLanguage, streaming]);

  if (!language) {
    // Inline code — unstyled, as before.
    return <code className={className}>{children}</code>;
  }

  return (
    <code
      className={className}
      dangerouslySetInnerHTML={{ __html: highlighted ?? escapeHtml(content) }}
    />
  );
};

const MarkdownContent: React.FC<{ content: string; streaming?: boolean }> = ({ content, streaming }) => (
  <div className="prose prose-sm max-w-none dark:prose-invert prose-pre:font-mono">
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code: (props) => <CodeBlock {...props} streaming={streaming} />,
      }}
    >
      {content}
    </ReactMarkdown>
  </div>
);

export default MarkdownContent;
