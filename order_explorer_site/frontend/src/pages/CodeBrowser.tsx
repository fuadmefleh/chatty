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
import './CodeBrowser.css';

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

  return (
    <div>
      <div
        className={`code-tree-row ${isDir ? 'dir' : 'file'}${selectedPath === entry.path ? ' selected' : ''}`}
        style={{ paddingLeft: 8 + depth * 14 }}
        onClick={() => (isDir ? onToggleDir(entry.path) : onSelectFile(entry.path))}
      >
        <span className="glyph">{isDir ? (isExpanded ? '▾' : '▸') : ''}</span>
        <span className="name">{entry.name}</span>
        {!isDir && <span className="file-size">{formatSize(entry.size)}</span>}
      </div>
      {isDir && isExpanded && (
        <div>
          {isLoading && (
            <div className="code-tree-row" style={{ paddingLeft: 8 + (depth + 1) * 14, color: 'var(--muted)' }}>
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
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Assistant / Code" eyebrowColor="var(--stamp-teal)" title="Code" />

      <div className="code-browser-layout">
        <Card padding={0}>
          <div className="code-tree-panel">
            {rootLoading ? (
              <p style={{ color: 'var(--muted)', padding: 8, fontSize: 13 }}>Loading…</p>
            ) : rootError ? (
              <p style={{ color: 'var(--danger)', padding: 8, fontSize: 13 }}>{rootError}</p>
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

        <Card padding={0}>
          <div className="code-content-panel">
            {selectedPath && (
              <div className="code-content-header">
                <span>{selectedPath}</span>
                {fileData && <span className="file-size">{formatSize(fileData.size)}</span>}
              </div>
            )}
            {!selectedPath ? (
              <div className="code-empty-state">Select a file to preview its contents.</div>
            ) : fileLoading ? (
              <div className="code-empty-state">Loading…</div>
            ) : fileError ? (
              <div className="code-error-state">{fileError}</div>
            ) : fileData ? (
              <div className="code-viewer">
                <pre className="line-numbers">{lineNumbers}</pre>
                <pre className="code-body">
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
