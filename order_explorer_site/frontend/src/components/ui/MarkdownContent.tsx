import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MarkdownContent: React.FC<{ content: string }> = ({ content }) => (
  <div className="prose prose-sm max-w-none dark:prose-invert prose-pre:font-mono">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
  </div>
);

export default MarkdownContent;
