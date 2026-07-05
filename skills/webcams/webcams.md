# Webcams

## Description
Tracks a list of live public webcam sources (traffic cams, city/tourism live views, etc.) that the user has manually added or approved from an auto-discovered suggestion. This skill is read-only - it can tell you what webcams are known about, but it does not fetch, view, or analyze any image/video content from them (that's a separate, not-yet-built feature).

New sources are managed from the dashboard's Webcams page: added manually, or discovered by a periodic background search (via SearXNG) that curates candidate webcams for the user to approve or dismiss.

## Usage
When the user asks what webcams/live cams are available, optionally about a specific place, list the enabled sources. Do not claim to have seen or analyzed what's currently showing on a cam - only report the name/location/kind/url metadata.

## Examples
- "What webcams do we have?"
- "Do we have any live cams of NYC?"
- "What live views do you know about in Tokyo?"

## Tools

### list_webcam_sources
Lists enabled webcam sources, optionally filtered by a location/name substring.

**Parameters:**
- `location_filter` (string, optional): Substring to filter by location or name (e.g. "NYC")

**Returns:** List of sources with name, location, kind, and url
