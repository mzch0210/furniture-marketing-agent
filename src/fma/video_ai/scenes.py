from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from ..models import CatalogProduct


@dataclass(frozen=True)
class ScenePreset:
    key: str
    room: str
    style: str
    palette: str
    lighting: str
    set_dressing: str


SCENE_PRESETS: dict[str, ScenePreset] = {
    "bedroom": ScenePreset(
        key="bedroom",
        room="a calm, premium American bedroom",
        style="warm contemporary with restrained mid-century details",
        palette="warm ivory, natural oak, muted taupe and soft linen",
        lighting="soft natural morning window light with realistic contact shadows",
        set_dressing="a neatly made bed, subtle bedside styling, a textured rug and uncluttered walls",
    ),
    "living_room": ScenePreset(
        key="living_room",
        room="a refined, lived-in American living room",
        style="modern organic with clean architectural lines",
        palette="warm neutrals, natural wood, muted earth tones and soft textiles",
        lighting="late-afternoon window light with gentle realistic shadows",
        set_dressing="a neutral rug, restrained wall art, a few plants and minimal accessories",
    ),
    "dining_room": ScenePreset(
        key="dining_room",
        room="a welcoming contemporary American dining room",
        style="modern transitional, understated and practical",
        palette="warm white, natural oak, soft beige and muted charcoal accents",
        lighting="diffused daylight with balanced interior fill",
        set_dressing="simple table styling, understated pendant lighting and uncluttered surroundings",
    ),
    "home_office": ScenePreset(
        key="home_office",
        room="a bright, organized contemporary home office",
        style="quiet modern with warm natural materials",
        palette="warm white, natural wood, muted sage and soft gray",
        lighting="clear indirect daylight with realistic desk shadows",
        set_dressing="minimal desk accessories, a neutral rug and a clean background",
    ),
    "entryway": ScenePreset(
        key="entryway",
        room="a welcoming contemporary home entryway",
        style="modern organic with subtle premium details",
        palette="warm ivory, natural wood, sand and muted black accents",
        lighting="soft daylight from the side with realistic contact shadows",
        set_dressing="a simple mirror, understated wall art and minimal decor",
    ),
    "studio": ScenePreset(
        key="studio",
        room="a premium neutral furniture photography studio",
        style="editorial product photography",
        palette="warm off-white, beige and natural stone",
        lighting="large softbox lighting with realistic floor contact shadows",
        set_dressing="a seamless warm neutral background with no distracting props",
    ),
}

_CATEGORY_PRESETS = {
    "bedroom": {
        "BED", "BED_FRAME", "HEADBOARD", "MATTRESS", "DRESSER",
        "CHEST_OF_DRAWERS", "NIGHTSTAND", "WARDROBE", "VANITY",
    },
    "living_room": {
        "SOFA", "SOFA_BED", "LOVESEAT", "FUTON", "RECLINER", "CHAIR",
        "ARMCHAIR", "OTTOMAN", "COFFEE_TABLE", "END_TABLE", "SIDE_TABLE",
        "TV_STAND", "BOOKCASE", "BOOKSHELF", "CABINET", "CREDENZA",
    },
    "dining_room": {
        "DINING_TABLE", "DINING_CHAIR", "BAR_STOOL", "BENCH", "TABLE",
    },
    "home_office": {"DESK", "OFFICE_CHAIR", "COMPUTER_DESK", "WRITING_DESK"},
    "entryway": {"CONSOLE_TABLE", "SHOE_RACK"},
}


def resolve_scene_preset(category: str, requested: str = "auto") -> ScenePreset:
    """Resolve an explicit or category-aware furniture room preset."""
    key = requested.strip().lower()
    if key != "auto":
        if key not in SCENE_PRESETS:
            raise ValueError(f"Unknown scene preset: {requested}")
        return SCENE_PRESETS[key]

    normalized = re.sub(r"[^A-Z0-9_]+", "_", category.upper()).strip("_")
    for preset_key, categories in _CATEGORY_PRESETS.items():
        if normalized in categories:
            return SCENE_PRESETS[preset_key]
    return SCENE_PRESETS["studio"]


def select_product_reference_images(
    product: CatalogProduct,
    limit: int = 10,
) -> list[dict[str, str]]:
    """Return distinct HTTPS product image references, main image first."""
    if not 1 <= limit <= 30:
        raise ValueError("Seedance accepts between 1 and 30 product reference images; Runway Product Ad accepts at most 10.")
    role_order = {"main_image": 0, "other_image": 1}
    candidates = sorted(
        (asset for asset in product.assets if asset.role in role_order and asset.source_uri),
        key=lambda asset: role_order[asset.role],
    )
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for asset in candidates:
        uri = str(asset.source_uri).strip()
        parsed = urlsplit(uri)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            continue
        if uri in seen:
            continue
        seen.add(uri)
        selected.append({"uri": uri, "asset_id": asset.asset_id, "role": asset.role})
        if len(selected) >= limit:
            break
    return selected


def build_product_info(product: CatalogProduct) -> str:
    """Describe only catalog-supplied identity; never infer missing product attributes."""
    parts = [
        f"Catalog product name: {product.name}",
        f"Catalog category: {product.category}",
    ]
    if product.brand:
        parts.append(f"Catalog brand field: {product.brand}")
    if product.description:
        parts.append(f"Source-reported catalog description: {product.description[:1400]}")
    parts.append(
        "All catalog fields are source-reported and may be incomplete. "
        "Do not invent dimensions, materials, functions, construction, certifications or included accessories."
    )
    return "\n".join(parts)[:2500]


def build_scene_concept(
    product: CatalogProduct,
    preset: ScenePreset,
    duration_seconds: int,
) -> str:
    """Build a conservative scene/camera brief bounded by the supplied product references."""
    return (
        f"Create a polished vertical {duration_seconds}-second furniture product advertisement. "
        f"Place the referenced {product.category.lower()} in {preset.room}. "
        f"Interior direction: {preset.style}; palette: {preset.palette}; "
        f"lighting: {preset.lighting}; surrounding set: {preset.set_dressing}. "
        "The supplied product photos are the only source of truth for the furniture. "
        "Preserve the exact product silhouette, visible geometry, proportions, color, finish, "
        "hardware, panel layout, drawer/door count, legs and other visible construction details. "
        "Do not redesign, embellish, simplify, add, remove or replace any product component. "
        "Do not show unseen sides or hidden construction as if verified; use only views supported "
        "by the supplied references. Keep the complete product visible and unobstructed. "
        "Use a slow cinematic push-in and a restrained lateral camera move; avoid a fake 360-degree "
        "orbit when the references do not show all sides. Make the room feel photorealistic and "
        "appropriately scaled, with natural contact shadows and consistent perspective. "
        "No people, no floating objects, no added accessories attached to the product, "
        "no on-screen text, no logos and no watermark. The room is illustrative; product attributes "
        "remain limited to the source images and catalog record."
    )


def scene_preset_manifest(preset: ScenePreset) -> dict[str, str]:
    return asdict(preset)
