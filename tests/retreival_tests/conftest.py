import json
import pytest
from pathlib import Path

from src.retreival.provider_class import BaseProvider


class DummyConfig:
    source = "TEST"
    url = "https://example.com"
    limit = 5


class DummyProvider(BaseProvider):
    def build_request(self, *args, **kwargs):
        return {}, {}

    def normalize(self, results):
        return results


@pytest.fixture
def taxonomy_file(tmp_path: Path):
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps({
        "museum": ["museum"]
    }))
    return path


@pytest.fixture
def provider(taxonomy_file):
    DummyConfig.taxonomy_path = taxonomy_file
    return DummyProvider(DummyConfig)