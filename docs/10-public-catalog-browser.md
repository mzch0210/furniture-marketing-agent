# Public Product Catalog Browser

Issue #10 adds a read-only local catalog browser over the normalized product sample produced by the ABO adapter. It reuses CatalogProduct, CatalogProductFact and CatalogAssetReference; it does not introduce a second product schema.

## 1. Import the sample

~~~bash
pip install -e ".[dev]"
python -m fma.data_sources.abo --data-dir data/public/abo --limit 30
~~~

The browser reads products.json and dataset-manifest.json from the processed/ directory. It does not silently download data or infer missing product attributes.

## 2. Start the browser

~~~bash
fma-catalog
# or
uvicorn fma.app:app --host 127.0.0.1 --port 8000
~~~

Open http://127.0.0.1:8000. The default data directory is data/public/abo. Set FMA_ABO_DATA_DIR to use a different ABO data directory.

## 3. Browser behavior

- Search by SKU, product name, brand, category, marketplace or source fact text.
- Filter by category and marketplace; paginate the local sample.
- Select a SKU to inspect normalized fields, source facts, verification status, source record ID, raw-record SHA-256 and source shard.
- Preview the main catalog image when the image metadata index supplied an official image URL. The image is loaded from the official ABO S3 host; image binaries are not copied into the repository or fetched by the browser backend.
- Open the official source metadata shard and image asset source.
- Missing tracked fields are explicitly displayed as Unknown. They are never guessed from product images or descriptions.
- Display the dataset name, license identifier, license verification state, official license link, attribution, paper citation and rights/no-endorsement notes from the manifest.

A source_reported fact is a value present in the public listing, not a factory-verified claim. unverified, factory_verified and rejected statuses are also rendered distinctly if later adapters or review workflows provide them.

## 4. Local API

- GET /api/catalog/status
- GET /api/catalog/products?q=&category=&marketplace=&limit=24&offset=0
- GET /api/catalog/products/{sku_or_id}
- GET /api/catalog/manifest

The API is read-only. Missing local data returns HTTP 503 with an instruction to import the ABO sample first.

## 5. Rights and data integrity

The UI presents the manifest's current license verification record and the known Registry metadata discrepancy. It does not imply that CC BY 4.0 clears third-party trademarks, privacy, publicity or other rights. It does not imply Amazon or UC Berkeley endorsement. Product catalog claims remain source-reported and must be independently confirmed by the factory before use as verified marketing claims.
