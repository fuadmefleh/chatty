import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  fetchBlogPosts,
  fetchBlogPost,
  fetchBlogStatus,
  generateBlogDraft,
  updateBlogPost,
  publishBlogPost,
  unpublishBlogPost,
  deleteBlogPost,
  type ChattyBlogPost,
  type BlogGenerationStatus,
} from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import EmptyState from '../components/ui/EmptyState';
import { useToast } from '../hooks/useToast';

const POLL_MS = 4000;

const stripHtml = (html: string): string => {
  const el = document.createElement('div');
  el.innerHTML = html;
  // Turn block boundaries into blank lines so the markdown starting point reads
  // like paragraphs rather than one run-on blob.
  return (el.textContent ?? '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
};

const formatDate = (iso: string | null): string => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return iso;
  }
};

interface EditState {
  title: string;
  excerpt: string;
  body: string;
  bodyTouched: boolean;
}

const ChattyBlog: React.FC = () => {
  const { showToast } = useToast();
  const [posts, setPosts] = useState<ChattyBlogPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<BlogGenerationStatus | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedHtml, setExpandedHtml] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<string | null>(null);
  const [edit, setEdit] = useState<EditState | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadPosts = useCallback(async () => {
    try {
      setPosts(await fetchBlogPosts('all'));
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to load posts', 'red');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await fetchBlogStatus());
    } catch {
      /* status is best-effort */
    }
  }, []);

  useEffect(() => {
    void loadPosts();
    void loadStatus();
  }, [loadPosts, loadStatus]);

  // While a generation is in flight, poll status; when it settles, refresh the
  // list so the new draft appears (or the error surfaces).
  useEffect(() => {
    if (!status?.generating) {
      if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    if (pollRef.current) return;
    pollRef.current = window.setInterval(async () => {
      const next = await fetchBlogStatus();
      setStatus(next);
      if (!next.generating) {
        if (next.error) showToast(`Generation failed: ${next.error}`, 'red');
        else showToast('New draft ready for review', 'signal');
        void loadPosts();
      }
    }, POLL_MS);
    return () => {
      if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [status?.generating, loadPosts, showToast]);

  const onGenerate = async () => {
    try {
      await generateBlogDraft();
      showToast('Chatty is writing a draft…', 'signal');
      await loadStatus();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Could not start generation', 'red');
    }
  };

  const toggleExpand = async (post: ChattyBlogPost) => {
    if (expandedId === post.id) { setExpandedId(null); return; }
    setExpandedId(post.id);
    if (!expandedHtml[post.id]) {
      try {
        const full = await fetchBlogPost(post.id);
        setExpandedHtml((prev) => ({ ...prev, [post.id]: full.html ?? '' }));
      } catch {
        showToast('Could not load post body', 'red');
      }
    }
  };

  const startEdit = async (post: ChattyBlogPost) => {
    let body = expandedHtml[post.id];
    if (body === undefined) {
      try {
        const full = await fetchBlogPost(post.id);
        body = full.html ?? '';
        setExpandedHtml((prev) => ({ ...prev, [post.id]: body }));
      } catch {
        body = '';
      }
    }
    setEditingId(post.id);
    setEdit({ title: post.title, excerpt: post.excerpt, body: stripHtml(body), bodyTouched: false });
  };

  const saveEdit = async (post: ChattyBlogPost) => {
    if (!edit) return;
    setBusyId(post.id);
    try {
      const payload: { title?: string; excerpt?: string; markdown?: string } = {
        title: edit.title,
        excerpt: edit.excerpt,
      };
      if (edit.bodyTouched) payload.markdown = edit.body;
      await updateBlogPost(post.id, payload);
      showToast('Draft updated', 'signal');
      setEditingId(null);
      setEdit(null);
      setExpandedHtml((prev) => { const n = { ...prev }; delete n[post.id]; return n; });
      await loadPosts();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Update failed', 'red');
    } finally {
      setBusyId(null);
    }
  };

  const onPublish = async (post: ChattyBlogPost) => {
    if (!window.confirm(`Publish "${post.title}" to the public blog now?`)) return;
    setBusyId(post.id);
    try {
      await publishBlogPost(post.id);
      showToast('Published', 'signal');
      await loadPosts();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Publish failed', 'red');
    } finally {
      setBusyId(null);
    }
  };

  const onUnpublish = async (post: ChattyBlogPost) => {
    setBusyId(post.id);
    try {
      await unpublishBlogPost(post.id);
      showToast('Pulled back to draft', 'amber');
      await loadPosts();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Unpublish failed', 'red');
    } finally {
      setBusyId(null);
    }
  };

  const onReject = async (post: ChattyBlogPost) => {
    if (!window.confirm(`Delete "${post.title}"? This cannot be undone.`)) return;
    setBusyId(post.id);
    try {
      await deleteBlogPost(post.id);
      showToast('Draft rejected', 'amber');
      await loadPosts();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Delete failed', 'red');
    } finally {
      setBusyId(null);
    }
  };

  const drafts = posts.filter((p) => p.status === 'draft');
  const published = posts.filter((p) => p.status === 'published');

  const renderCard = (post: ChattyBlogPost) => {
    const isEditing = editingId === post.id;
    const isExpanded = expandedId === post.id;
    const busy = busyId === post.id;

    return (
      <Card key={post.id} className="mb-3">
        {isEditing && edit ? (
          <div className="flex flex-col gap-3">
            <label className="text-xs font-semibold uppercase tracking-wide text-muted">Title</label>
            <input
              value={edit.title}
              onChange={(e) => setEdit({ ...edit, title: e.target.value })}
              className="rounded-lg border border-line bg-transparent px-3 py-2 text-sm text-ink"
            />
            <label className="text-xs font-semibold uppercase tracking-wide text-muted">Excerpt</label>
            <textarea
              value={edit.excerpt}
              onChange={(e) => setEdit({ ...edit, excerpt: e.target.value })}
              rows={2}
              className="rounded-lg border border-line bg-transparent px-3 py-2 text-sm text-ink"
            />
            <label className="text-xs font-semibold uppercase tracking-wide text-muted">
              Body (markdown){!edit.bodyTouched && ' — plain text from the rendered post; edit to replace'}
            </label>
            <textarea
              value={edit.body}
              onChange={(e) => setEdit({ ...edit, body: e.target.value, bodyTouched: true })}
              rows={14}
              className="rounded-lg border border-line bg-transparent px-3 py-2 font-mono text-xs leading-relaxed text-ink"
            />
            <div className="flex gap-2">
              <button
                onClick={() => saveEdit(post)}
                disabled={busy}
                className="h-9 rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-50"
              >
                {busy ? 'Saving…' : 'Save'}
              </button>
              <button
                onClick={() => { setEditingId(null); setEdit(null); }}
                className="h-9 rounded-lg border border-line px-4 text-sm font-medium text-ink-dim"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-base font-bold text-ink">{post.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink-dim">{post.excerpt}</p>
                <p className="mt-2 text-xs text-muted">
                  {post.status === 'published'
                    ? `Published ${formatDate(post.published_at)}`
                    : `Drafted ${formatDate(post.created_at)}`}
                </p>
              </div>
            </div>

            {isExpanded && (
              <div
                className="prose-blog mt-4 border-t border-line pt-4 text-sm leading-relaxed text-ink-dim [&_p]:mb-3"
                dangerouslySetInnerHTML={{ __html: expandedHtml[post.id] ?? '<p class="text-muted">Loading…</p>' }}
              />
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                onClick={() => toggleExpand(post)}
                className="h-9 rounded-lg border border-line px-3 text-sm font-medium text-ink-dim"
              >
                {isExpanded ? 'Hide' : 'Read'}
              </button>
              <button
                onClick={() => startEdit(post)}
                disabled={busy}
                className="h-9 rounded-lg border border-line px-3 text-sm font-medium text-ink-dim disabled:opacity-50"
              >
                Edit
              </button>
              {post.status === 'draft' ? (
                <>
                  <button
                    onClick={() => onPublish(post)}
                    disabled={busy}
                    className="h-9 rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-50"
                  >
                    {busy ? '…' : 'Approve & publish'}
                  </button>
                  <button
                    onClick={() => onReject(post)}
                    disabled={busy}
                    className="h-9 rounded-lg border border-alert-red/40 px-3 text-sm font-semibold text-alert-red disabled:opacity-50"
                  >
                    Reject
                  </button>
                </>
              ) : (
                <>
                  <a
                    href={post.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex h-9 items-center rounded-lg border border-line px-3 text-sm font-medium text-ink-dim"
                  >
                    View live
                  </a>
                  <button
                    onClick={() => onUnpublish(post)}
                    disabled={busy}
                    className="h-9 rounded-lg border border-alert-amber/40 px-3 text-sm font-semibold text-alert-amber disabled:opacity-50"
                  >
                    Unpublish
                  </button>
                </>
              )}
            </div>
          </>
        )}
      </Card>
    );
  };

  const nextDue = status?.next_due_at ? formatDate(status.next_due_at) : null;

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Writing"
        eyebrowColor="var(--signal)"
        title="Notes by Chatty"
        actions={
          <button
            onClick={onGenerate}
            disabled={status?.generating || status?.configured === false}
            className="h-9 rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-50"
          >
            {status?.generating ? 'Writing…' : 'Generate draft now'}
          </button>
        }
      />

      <Card className="mb-6">
        <p className="text-sm leading-relaxed text-ink-dim">
          Chatty writes short reflective essays on its own, with no topic prompting. Every post lands here as a{' '}
          <span className="font-semibold text-ink">pending draft</span> — nothing goes public until you approve it.
        </p>
        <p className="mt-2 text-xs text-muted">
          {status?.configured === false
            ? 'Blog API token not configured — generation is disabled.'
            : nextDue
              ? `Next automatic draft around ${nextDue}.`
              : 'The first automatic draft will appear within the writing interval.'}
        </p>
      </Card>

      {loading ? (
        <EmptyState title="Loading…" description="Fetching Chatty's posts." />
      ) : (
        <>
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-muted">
            Pending drafts{drafts.length > 0 && ` (${drafts.length})`}
          </h2>
          {drafts.length === 0 ? (
            <EmptyState
              title="No drafts waiting"
              description="When Chatty writes, its drafts appear here for your review."
            />
          ) : (
            drafts.map(renderCard)
          )}

          <h2 className="mb-3 mt-8 text-sm font-bold uppercase tracking-wide text-muted">
            Published{published.length > 0 && ` (${published.length})`}
          </h2>
          {published.length === 0 ? (
            <EmptyState title="Nothing published yet" description="Approved posts show up here." />
          ) : (
            published.map(renderCard)
          )}
        </>
      )}
    </div>
  );
};

export default ChattyBlog;
