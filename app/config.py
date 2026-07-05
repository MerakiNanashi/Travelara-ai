from pydantic_settings import BaseSettings, SettingsConfigDict

latlon_path = r'./data/latlon/cities500.txt' # fill in the path for cities500.txt data
in_latlon_path = r'./data/latlon/IN.txt' # fill in the path for IN.txt

FS_cat = r'./data/providers_taxamony/foursquare_categories.json'
GA_cat = r'./data/providers_taxamony/geoapify_categories.json'

model = "gemini-2.5-flash-lite"  
model_thinking = "gemini-2.5-flash"  

class Settings(BaseSettings):
    gemini_api_key: str = ""
    geoapify_api_key: str = ""
    foursquare_api_key: str = ""

    # Planning defaults
    knn_k: int = 10
    max_anchors: int = 6
    beam_width: int = 3
    anchor_radius_km: float = 2.0
    refinement_iterations: int = 3

    model_config = SettingsConfigDict(
        env_file=r"./.env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()