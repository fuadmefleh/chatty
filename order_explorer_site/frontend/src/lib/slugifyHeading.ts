// Shared between MarkdownContent's heading-anchor override and WikiArticle's
// Contents box, which parses the same headings from raw markdown and must
// produce identical slugs for the anchor links to actually land.
export const slugifyHeading = (text: string): string =>
  text.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
