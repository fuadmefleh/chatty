# Webcams

## Description
Tracks a list of live public webcam sources (traffic cams, city/tourism live views, etc.) that the user has manually added or approved from an auto-discovered suggestion, and can actually pull one up so the user watches it live. Every source is fetched and checked (see `verify_status`) before it's trusted as playable - both when it's added/approved and on an ongoing daily recheck - so only links Chatty has confirmed actually work are offered for viewing.

New sources are managed from the dashboard's Webcams page: added manually, or discovered by a periodic background search (via SearXNG) that curates candidate webcams, verifies each one is actually playable, and only then lists it for the user to approve or dismiss.

## Usage
When the user asks what webcams/live cams are available, optionally about a specific place, list the enabled sources (list_webcam_sources). Do not claim to have seen or analyzed what's currently showing on a cam - only report the name/location/kind/url/verify_status metadata.

When the user asks to see/watch/pull up/show a specific cam, use `open_webcam_stream` and paste its `markdown` field verbatim into your reply - it renders as an actual live player (an image feed, or an inline video/embed) for the user, not just a link. If `open_webcam_stream` reports no match or a broken/unverified source, say so plainly rather than inventing a URL.

## Examples
- "What webcams do we have?"
- "Do we have any live cams of NYC?"
- "What live views do you know about in Tokyo?"
- "Show me the Times Square cam" → use open_webcam_stream, paste its markdown verbatim
- "Pull up that traffic cam in Chicago" → use open_webcam_stream, paste its markdown verbatim

## Tools

### list_webcam_sources
Lists enabled webcam sources, optionally filtered by a location/name substring.

**Parameters:**
- `location_filter` (string, optional): Substring to filter by location or name (e.g. "NYC")

**Returns:** List of sources with name, location, kind, url, and verify_status

### open_webcam_stream
Resolves a webcam by name/location and returns markdown that actually shows the live feed when pasted into a reply verbatim.

**Parameters:**
- `name_or_location` (string, required): Substring to match against a source's name or location

**Returns:** `{success, embeddable, markdown}` on match (paste `markdown` as-is), or `{success: false, error}` if nothing matches or the best match isn't confirmed playable.
