from __future__ import annotations

from src.shared.schemas import StructuredIntent, _ProviderConfig
from src.retreival.foursquare_provider import FoursquareProvider
from src.retreival.geoapify_provider import GeoapifyProvider
from src.retreival.internals import retrieve_latlon

from src.shared.adapters import intent_adapter

def build_providers(config, settings):
    providers = {}

    for provider in config["providers"]:
        cfg = _ProviderConfig(**provider)

        if cfg.source == "GA":
            providers[cfg.source] = GeoapifyProvider(cfg, settings.geoapify_api_key)
        else:
            providers[cfg.source] = FoursquareProvider(cfg, settings.foursquare_api_key)

    return providers

def get_params(intent: StructuredIntent,
               config: dict):
    is_international = intent_adapter.is_international(intent)
    destination = intent_adapter.destination(intent)

    resolver = config["long_resolve"]
    lat, lon = retrieve_latlon(
        destination,
        resolver['gl_path'] if is_international 
        else resolver['dom_path']
    )
    walking_limit = int(intent_adapter.walking_limit_km(intent))

    prefs = intent.preferences
    radius_m = int(walking_limit or 10) * 1500

    return lat, lon, radius_m, prefs

def build_pois(intent: StructuredIntent,):
    must_avoid = set(intent_adapter.avoid_categories(intent))
    # filter pois based on constraints
    pass