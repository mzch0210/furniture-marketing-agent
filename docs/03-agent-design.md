# Agent Design

## Pattern
Orchestrator + specialized Agents + deterministic tools + human approval. Avoid one oversized prompt with no checkpoints.

## Roles
- Orchestrator: state, routing, retries, audit events and approvals.
- Product Agent: extract candidate SKU facts with source references and verification state.
- Market Agent: audience, market context, language conventions and sourced content opportunities.
- Strategy Agent: objective, audience, angle, benefit, proof points, hook and CTA.
- Creative Agent: English script, voiceover, captions, storyboard and shot list.
- Production Agent: asset search, shot matching, missing-shot list, EDL, enhancement and render adapters.
- Quality Agent: product truth, provenance, visual consistency, technical specs, subtitles, audio and marketing clarity.

## Structured shot output
Each shot should include index, target duration, purpose, visual description, required product view, source asset IDs, on-screen text, voiceover, edit instruction, confidence and missing-footage flag.

## Approval policy
Require human approval for new product facts, commercial commitments, material/safety/certification claims, potentially misleading AI enhancement and final publication. Reuse previously approved facts only within their approved scope.

## First demo
Build the narrow path first: Product facts → Creative script/storyboard → real asset matching → EDL/render → QC → human approval. Use one real SKU and factory-approved footage.