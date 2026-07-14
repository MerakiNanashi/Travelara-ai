import pytest
from unittest.mock import AsyncMock, patch


def test_init_loads_config(provider):
    assert provider.source == "TEST"
    assert provider.url == "https://example.com"
    assert provider.limit == 5

def test_loads_taxonomy(provider):
    assert provider.category_map == {
        "museum": ["museum"]
    }


@patch("src.retreival.provider_class.POI")
def test_create_poi(mock_poi, provider):
    provider.create_poi(name="A")

    mock_poi.assert_called_once()

    kwargs = mock_poi.call_args.kwargs

    assert kwargs["name"] == "A"
    assert kwargs["source"] == "TEST"


@pytest.mark.asyncio
async def test_fetch_category(provider):

    response = AsyncMock()
    response.status_code = 200
    response.json.return_value = {"results": []}

    client = AsyncMock()
    client.get.return_value = response

    category, payload = await provider.fetch_category(
        client,
        "museum",
        ["museum"],
        1,
        2,
        500,
    )

    assert category == "museum"
    assert payload == {"results": []}

    client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_category_http_error(provider):

    response = AsyncMock()
    response.status_code = 500
    response.text = "error"

    response.raise_for_status.side_effect = RuntimeError

    client = AsyncMock()
    client.get.return_value = response

    with pytest.raises(RuntimeError):
        await provider.fetch_category(
            client,
            "museum",
            ["museum"],
            1,
            2,
            500,
        )


@pytest.mark.asyncio
@patch("src.retreival.provider_class.get_categorymap")
@patch("src.retreival.provider_class.preferences_to_legacy")
async def test_retrieve(
    legacy,
    category_map,
    provider,
):

    legacy.return_value = {"museum": 1}

    category_map.return_value = {
        "museum": ["museum"]
    }

    provider.fetch = AsyncMock(return_value={"museum": {}})
    provider.normalize = lambda x: ["poi"]

    result = await provider.retrieve(
        lat=1,
        lon=2,
        prefs=[],
    )

    assert result == ["poi"]