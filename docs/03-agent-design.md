# Agent Design

## 1. Design pattern

Use Orchestrator + specialized Agents + deterministic tools + human approval. Agents return schema-validated proposals; deterministic services own data validation, media rendering, permissions and state transitions.

## 2. Full product Agent roles

### Orchestrator
Owns workflow state, routing, retries, audit events, approval gates and job status. It does not invent product facts.

### Product Agent
Imports and interprets product catalog data, extracts candidate facts, normalizes attributes and attaches source references and verification states. It distinguishes source-reported claims from factory-confirmed facts.

### Market Agent
Researches target markets, audience language, competitors and content opportunities. External findings retain source URLs and retrieval dates. It must distinguish evidence from hypotheses.

### Strategy Agent
Converts campaign objective and audience into positioning, message hierarchy, content angles, proof points, CTA and testable creative hypotheses.

### Creative Agent
Generates localized scripts, voiceover, on-screen text, captions, storyboards and shot lists. It returns structured, time-bounded outputs.

### Production Agent
Searches the asset library, maps storyboard shots to source assets, detects missing coverage, proposes reshoots, prepares an edit decision list and invokes enhancement/render adapters.

### Quality Agent
Checks claim provenance, product identity, visual fidelity, subtitles, audio, pacing, duration, aspect ratio, codec, file integrity and campaign requirements. It can block approval.

## 3. Public Data Demo implementation subset

Implement a working vertical slice using the same contracts:

1. Product Agent: ABO adapter → normalized product and source-backed facts.
2. Strategy Agent: deterministic English-market templates for B2B/B2C objective, audience and angle.
3. Creative Agent: deterministic script/storyboard/caption templates; optional LLM adapter can be added without making an API key mandatory.
4. Production Agent: select catalog images or 360° frames, map them to shots, mark missing live-action footage and build an edit decision list.
5. Quality Agent: validate source links, unverified claims, output file integrity, duration, resolution, frame rate, subtitles and required CTA.
6. Orchestrator: coordinate the local workflow and expose approval states.

The Market Agent's full research capability is not required for the first Demo. Use a transparent, preconfigured US-English audience/content assumption rather than pretending to have performed live market research.

## 4. Structured shot contract

Each storyboard shot includes:
- shot index and target duration
- narrative purpose
- visual description
- required product view
- matched source asset IDs
- source type: image, 360 sequence or live-action video
- on-screen text and voiceover
- transition/edit instruction
- match confidence
- missing-footage flag and reshoot note

## 5. Product fact and approval policy

Every claim must reference one or more source facts. Unknown fields remain Unknown. Do not infer material, dimensions, load capacity, certifications, durability, included accessories, MOQ, lead time or warranty from an image or category label.

Require human approval for newly introduced product facts, commercial commitments, potentially misleading scene enhancement and final video. Public catalog facts must be labeled as source-reported, not factory-confirmed.
