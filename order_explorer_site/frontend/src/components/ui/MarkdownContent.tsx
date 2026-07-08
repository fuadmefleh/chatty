import { useMemo, Children, isValidElement } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Link } from 'react-router-dom';
import { highlight, escapeHtml } from '../../lib/prismHighlight';
import { slugifyHeading } from '../../lib/slugifyHeading';

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

// The wiki backend links pages to each other with relative paths of this
// exact shape (see src/core/wiki_store.py's _rel_path): "pages/entities/
// <slug>.md" or "pages/concepts/<slug>.md". Intercept just those and route
// them client-side to the article page instead of a dead file link; every
// other href (external, mailto, or any non-wiki relative path - e.g.
// arbitrary links inside a Chat.tsx message) falls through unchanged.
const WIKI_LINK_RE = /^pages\/(entities|concepts)\/([^/]+)\.md$/;
const TYPE_FROM_DIR: Record<string, string> = { entities: 'entity', concepts: 'concept' };

const WikiAwareLink: React.FC<{ href?: string; children?: React.ReactNode }> = ({ href, children }) => {
  const match = href ? WIKI_LINK_RE.exec(href) : null;
  if (match) {
    const [, typeDir, slug] = match;
    return <Link to={`/memory/${TYPE_FROM_DIR[typeDir]}/${slug}`}>{children}</Link>;
  }
  return (
    <a href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
};

// Flattens a heading's rendered children (which may include nested inline
// elements like <code>/<em>) down to plain text, so it can be slugified into
// an anchor id for the wiki article's Contents box.
const headingText = (children: React.ReactNode): string =>
  Children.toArray(children)
    .map((child) => {
      if (typeof child === 'string' || typeof child === 'number') return String(child);
      if (isValidElement<{ children?: React.ReactNode }>(child)) return headingText(child.props.children);
      return '';
    })
    .join('');

const MarkdownContent: React.FC<{ content: string; streaming?: boolean; anchorHeadings?: boolean }> = ({
  content,
  streaming,
  anchorHeadings,
}) => {
  const components: Components = {
    code: (props) => <CodeBlock {...props} streaming={streaming} />,
    a: (props) => <WikiAwareLink {...props} />,
  };

  if (anchorHeadings) {
    components.h2 = ({ children }) => <h2 id={slugifyHeading(headingText(children))}>{children}</h2>;
    components.h3 = ({ children }) => <h3 id={slugifyHeading(headingText(children))}>{children}</h3>;
  }

  return (
    <div className="prose prose-sm max-w-none dark:prose-invert prose-pre:font-mono">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownContent;
