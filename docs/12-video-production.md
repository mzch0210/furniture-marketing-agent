# Issue #12 — Public Asset Matching, EDL and Vertical MP4 Rendering

This module turns an Issue #11 creative package into a playable vertical MP4 using selected public catalog images. It is the public-data Demo renderer, not the future real-footage-first factory production system.

## Install

FFmpeg and ffprobe must be installed and available on PATH. The renderer uses FFmpeg \`drawtext\`, \`scale\`, \`pad\` and \`zoompan\` filters.

- Windows: install an FFmpeg build from https://ffmpeg.org/download.html and add its \`bin\` directory to PATH.
- macOS: \`brew install ffmpeg\`
- Ubuntu/Debian: \`sudo apt-get update && sudo apt-get install -y ffmpeg fonts-dejavu-core\`

The renderer needs a TrueType font. It checks common DejaVu Sans / Liberation Sans / Arial paths; set \`FMA_FONT_FILE\` if your font is elsewhere.

## Import the public catalog

~~~bash
pip install -e ".[dev]"
python -m fma.data_sources.abo --data-dir data/public/abo --limit 30
~~~

The importer downloads the public listings, official license text and image metadata index. It does not download the full image archive.

## Generate the MP4

~~~bash
fma-render --sku YOUR_IMPORTED_SKU --data-dir data/public/abo --output-dir data/renders --audience B2C --objective product_consideration --angle product_overview --duration 30
~~~

Replace \`YOUR_IMPORTED_SKU\` with a SKU from the local catalog. The command:
1. Generates the deterministic English campaign brief, script and storyboard.
2. Resolves the storyboard's candidate product images.
3. Tries the original-resolution object path first and falls back to the official 256px small image.
4. Downloads only selected images for this SKU; it never downloads the full image archive.
5. Writes an editable EDL and a reshoot checklist for unmatched product shots.
6. Renders a 1080×1920, 30fps, H.264 MP4 and validates the output with ffprobe.

Default output: \`data/renders/{campaign_id}/{sku}/video.mp4\`. The folder also contains \`edit-decision-list.json\`, \`render-report.json\`, \`reshoot-checklist.md\` and \`rights-review.md\`. Creative files remain under \`data/outputs/creatives/\`.

## API

\`POST /api/video/render\` accepts the same request body as \`/api/creative/generate\`:

~~~json
{
  "sku": "YOUR_IMPORTED_SKU",
  "audience": "B2C",
  "objective": "product_consideration",
  "angle": "product_overview",
  "target_market": "United States",
  "platform": "TikTok",
  "language": "en-US",
  "duration_seconds": 30
}
~~~

This local endpoint renders synchronously and is intended for the single-user Demo. A queued job API is a later production concern.

## Media matching and truthful output

- Only HTTPS objects on the official ABO S3 host are downloaded. Redirects to other hosts, non-image content and files above the size limit are rejected.
- The original-resolution URL is derived only from a validated official \`images/small/\` path. The small image is the fallback.
- Every downloaded asset records its source URI, selected variant, SHA-256, byte size, dataset, record ID and license identifier in the EDL.
- The first three product-focused shots use a matched catalog image or are marked \`missing\`; missing shots render as visible placeholders and appear in the reshoot checklist.
- Trust/CTA beats are generated title cards and do not pretend to be product footage.
- Still images receive subtle pan/zoom motion. This output is explicitly \`catalog_still_image_animation\`, not factory-shot live-action.
- The current first renderer produces a silent MP4. Voiceover text and SRT remain available from Issue #11; no unlicensed music or synthetic voice is added.
- 360° spin IDs are retained as candidate metadata, but this first vertical slice uses still images. Turntable-frame rendering can follow after the first usable MP4 is validated.

## Rights and attribution

The current official ABO dataset landing page and downloaded license file state CC BY 4.0. The AWS Registry page surfaced a conflicting CC BY-NC 4.0 license entry. The EDL preserves the local manifest's license and attribution, adds a rights-review warning when the manifest records the conflict, and writes \`rights-review.md\`.

Use this build as an internal technical Demo. Do not externally redistribute or commercially use the rendered ABO media until the conflicting Registry metadata and any third-party image/trademark rights have been reviewed. CC BY attribution is included in the content pack; no Amazon/UC Berkeley endorsement is implied.

## Troubleshooting

- \`ffmpeg was not found\`: install FFmpeg and add it to PATH.
- \`drawtext filter unavailable\`: install a full FFmpeg build with libfreetype/drawtext.
- \`No supported TrueType font\`: install DejaVu Sans or set \`FMA_FONT_FILE\`.
- \`No downloadable official ABO image\`: re-import with the image metadata index; inspect the product's image asset URI; the shot is marked missing instead of being fabricated.
- \`Rendered MP4 metadata is incomplete\`: check FFmpeg/ffprobe versions and the renderer error.

## Scope boundary

No AI scene generation, TTS, music, automatic TikTok publishing, live market research or factory footage editing is included. Those remain outside the first public-data video-rendering slice.
