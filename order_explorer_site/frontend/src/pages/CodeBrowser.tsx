import React, { useEffect, useState } from 'react';
import axios from 'axios';
import Prism from 'prismjs';
import 'prismjs/components/prism-clike';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-jsx';
import 'prismjs/components/prism-tsx';
import 'prismjs/components/prism-markup';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-markdown';
import 'prismjs/components/prism-python';
import { fetchCodeTree, fetchCodeFile } from '../chattyApi';
import type { CodeTreeEntry, CodeFile } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';

const formatSize = (bytes: number | null): string => {
  if (bytes === null) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const escapeHtml = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const highlight = (content: string, language: string): string => {
  const grammar = Prism.languages[language];
  if (!grammar) return escapeHtml(content);
  return Prism.highlight(content, grammar, language);
};

interface TreeNodeProps {
  entry: CodeTreeEntry;
  depth: number;
  expandedDirs: Set<string>;
  loadingDirs: Set<string>;
  treeCache: Record<string, CodeTreeEntry[]>;
  selectedPath: string | null;
  onToggleDir: (path: string) => void;
  onSelectFile: (path: string) => void;
}

const TreeNode: React.FC<TreeNodeProps> = ({
  entry, depth, expandedDirs, loadingDirs, treeCache, selectedPath, onToggleDir, onSelectFile,
}) => {
  const isDir = entry.type === 'dir';
  const isExpanded = isDir && expandedDirs.has(entry.path);
  const isLoading = isDir && loadingDirs.has(entry.path);
  const children = isDir ? treeCache[entry.path] : undefined;
  const isSelected = selectedPath === entry.path;

  return (
    <div>
      <div
        className={`flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border-l-2 py-[3px] px-2 font-mono text-[12.5px] hover:bg-surface-dim ${
          isSelected ? 'border-signal bg-surface-dim' : 'border-transparent'
        }`}
        style={{ paddingLeft: 8 + depth * 14 }}
        onClick={() => (isDir ? onToggleDir(entry.path) : onSelectFile(entry.path))}
      >
        <span className="w-3 shrink-0 text-muted">{isDir ? (isExpanded ? '▾' : '▸') : ''}</span>
        <span className={isDir ? 'font-semibold text-ink' : 'text-ink-dim'}>{entry.name}</span>
        {!isDir && <span className="ml-auto pl-3 text-[11px] text-muted">{formatSize(entry.size)}</span>}
      </div>
      {isDir && isExpanded && (
        <div>
          {isLoading && (
            <div
              className="py-[3px] px-2 font-mono text-[12.5px] text-muted"
              style={{ paddingLeft: 8 + (depth + 1) * 14 }}
            >
              loading…
            </div>
          )}
          {children?.map((child) => (
            <TreeNode
              key={child.path}
              entry={child}
              depth={depth + 1}
              expandedDirs={expandedDirs}
              loadingDirs={loadingDirs}
              treeCache={treeCache}
              selectedPath={selectedPath}
              onToggleDir={onToggleDir}
              onSelectFile={onSelectFile}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const CodeBrowser: React.FC = () => {
  const [treeCache, setTreeCache] = useState<Record<string, CodeTreeEntry[]>>({});
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [loadingDirs, setLoadingDirs] = useState<Set<string>>(new Set());
  const [rootLoading, setRootLoading] = useState(true);
  const [rootError, setRootError] = useState('');

  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [fileData, setFileData] = useState<CodeFile | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState('');

  // Below the `lg` breakpoint the tree and the code viewer are two separate
  // views the user switches between (list → detail) rather than two squeezed
  // side-by-side panels. Ignored entirely at `lg:` and above, where both
  // panels are always shown.
  const [mobileView, setMobileView] = useState<'tree' | 'code'>('tree');

  useEffect(() => {
    (async () => {
      try {
        const res = await fetchCodeTree('');
        setTreeCache((prev) => ({ ...prev, '': res.entries }));
        setExpandedDirs(new Set(['']));
      } catch {
        setRootError('Failed to load the code tree.');
      } finally {
        setRootLoading(false);
      }
    })();
  }, []);

  const loadDir = async (path: string) => {
    setLoadingDirs((prev) => new Set(prev).add(path));
    try {
      const res = await fetchCodeTree(path);
      setTreeCache((prev) => ({ ...prev, [path]: res.entries }));
    } catch {
      setTreeCache((prev) => ({ ...prev, [path]: [] }));
    } finally {
      setLoadingDirs((prev) => {
        const next = new Set(prev);
        next.delete(path);
        return next;
      });
    }
  };

  const handleToggleDir = (path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
        if (!(path in treeCache)) loadDir(path);
      }
      return next;
    });
  };

  const handleSelectFile = async (path: string) => {
    setSelectedPath(path);
    setMobileView('code');
    setFileLoading(true);
    setFileError('');
    setFileData(null);
    try {
      const data = await fetchCodeFile(path);
      setFileData(data);
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
      setFileError(detail || 'Failed to load file.');
    } finally {
      setFileLoading(false);
    }
  };

  const rootEntries = treeCache[''] ?? [];
  const lineCount = fileData ? fileData.content.split('\n').length : 0;
  const lineNumbers = Array.from({ length: lineCount }, (_, i) => i + 1).join('\n');

  return (
    <div className="mx-auto max-w-[1400px] px-4 pb-12 pt-6 md:px-6">
      <PageHeader eyebrow="Assistant / Code" eyebrowColor="var(--signal)" title="Code" />

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <Card
          padding={0}
          className={`w-full lg:block lg:w-[300px] lg:shrink-0 ${mobileView === 'tree' ? 'block' : 'hidden'}`}
        >
          <div className="max-h-[calc(100vh-160px)] overflow-y-auto p-2">
            {rootLoading ? (
              <div className="flex justify-center p-3">
                <Spinner size="sm" label="Loading tree…" />
              </div>
            ) : rootError ? (
              <p className="p-2 text-[13px] text-alert-red">{rootError}</p>
            ) : (
              rootEntries.map((entry) => (
                <TreeNode
                  key={entry.path}
                  entry={entry}
                  depth={0}
                  expandedDirs={expandedDirs}
                  loadingDirs={loadingDirs}
                  treeCache={treeCache}
                  selectedPath={selectedPath}
                  onToggleDir={handleToggleDir}
                  onSelectFile={handleSelectFile}
                />
              ))
            )}
          </div>
        </Card>

        <Card
          padding={0}
          className={`w-full min-w-0 lg:block lg:flex-1 ${mobileView === 'code' ? 'block' : 'hidden'}`}
        >
          <div className="max-h-[calc(100vh-160px)] overflow-auto">
            <button
              type="button"
              onClick={() => setMobileView('tree')}
              className="block w-full border-b border-line px-4 py-2.5 text-left font-mono text-[12.5px] font-medium text-signal hover:text-alert-amber lg:hidden"
            >
              ← Back to files
            </button>
            {selectedPath && (
              <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-line bg-surface-dim px-4 py-2.5 font-mono text-[12.5px] text-ink-dim">
                <span className="truncate">{selectedPath}</span>
                {fileData && <span className="shrink-0 text-muted">{formatSize(fileData.size)}</span>}
              </div>
            )}
            {!selectedPath ? (
              <div className="px-5 py-10">
                <EmptyState title="No file selected" description="Select a file from the tree to preview its contents." />
              </div>
            ) : fileLoading ? (
              <div className="flex justify-center px-5 py-10">
                <Spinner label="Loading file…" />
              </div>
            ) : fileError ? (
              <p className="px-5 py-10 text-center text-[13.5px] text-alert-red">{fileError}</p>
            ) : fileData ? (
              <div className="flex font-mono text-[12.5px] leading-[1.6]">
                <pre className="m-0 shrink-0 select-none whitespace-pre border-r border-line bg-surface-dim px-2.5 py-3 text-right text-muted">
                  {lineNumbers}
                </pre>
                <pre className="m-0 min-w-0 flex-1 overflow-x-auto px-4 py-3 text-ink-dim">
                  <code
                    dangerouslySetInnerHTML={{ __html: highlight(fileData.content, fileData.language) }}
                  />
                </pre>
              </div>
            ) : null}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default CodeBrowser;
