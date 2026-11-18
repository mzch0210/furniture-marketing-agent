# Public Data Demo Implementation Plan

**Repository purpose:** complete Furniture Marketing Agent product.  
**Current milestone:** Public Data Demo using public data only; not a throwaway prototype.

## Amazon Berkeley Objects (ABO)

Official dataset: https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html  
Official license: https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/LICENSE-CC-BY-4.0.txt  
AWS Registry: https://registry.opendata.aws/amazon-berkeley-objects/  
Registry source YAML: https://github.com/awslabs/open-data-registry/blob/main/datasets/amazon-berkeley-objects.yaml

The official landing page and the current Registry source YAML identify CC BY 4.0. A cached rendered Registry page snapshot was observed showing CC BY-NC; the adapter records this as stale rendered metadata. It downloads and verifies the official license text and stores its SHA-256 for each import. Recheck the exact source before redistribution. CC BY does not grant trademark, privacy, publicity or other third-party rights the licensor does not control and does not imply Amazon/UC Berkeley endorsement.

The official page reports 147,702 product listings and 398,212 unique catalog images. More than 8,200 products have 24- or 72-view turntable sequences; more than 7,900 have glTF 2.0 models.

### Download scope

- `archives/abo-listings.tar` — listings metadata, approximately 83 MB.
- `LICENSE-CC-BY-4.0.txt` — official license text.
- `images/metadata/images.csv.gz` — image IDs, dimensions and relative paths.
- Image, spin and 3D model binaries are not downloaded by this adapter.

The metadata schema uses `domain_name`, `item_name`, `product_type`, `node.path`, `main_image_id`, `other_image_id`, `spin_id` and `3dmodel_id`. The adapter inspects actual tar members and fails clearly if the expected gzip JSONL listing shards are absent.

### Run

```bash
pip install -e ".[dev]"
python -m fma.data_sources.abo --data-dir data/public/abo --limit 30
```

Use `--offline` to reuse downloaded files, `--all-marketplaces` to remove the default US marketplace filter, and `--skip-image-index` to skip the image metadata CSV.

### Provenance and product facts

Every imported fact retains its source dataset, item ID, shard URI, source field, original value, language and `source_reported` verification state. Missing values remain Unknown; no attributes are inferred from images. Image IDs are resolved through the official image metadata index. Raw data is stored under gitignored `data/public/abo/`.

Credit data and images to Amazon.com and dataset creators: Matthieu Guillaumin, Thomas Dideriksen, Kenan Deng, Himanshu Arora, Arnab Dhua, Xi (Brian) Zhang, Tomas Yago-Vicente, Jasmine Collins, Shubham Goel and Jitendra Malik.

For publication cite: Collins et al. (2022), “ABO: Dataset and Benchmarks for Real-World 3D Object Understanding”, CVPR 2022.

The generated manifest records license file hash, attribution, item/asset IDs, retrieval time and modifications. Catalog facts are not factory-verified.

## Acceptance

- Download official listings, license and image metadata only.
- Verify the license text and inspect archive members.
- Parse JSONL records and select a deterministic, category-balanced furniture sample.
- Resolve image references only through the official metadata CSV.
- Do not download image/spin/3D binary archives.
- Unit tests use synthetic archives; GitHub Actions performs a live archive smoke test.
