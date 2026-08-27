import httpx
import pytest

from catalog_forge.fetcher import FetchError, HttpFetcher, parse_retry_after, validate_public_url


@pytest.mark.asyncio
async def test_fetcher_classifies_429_and_retry_after() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "3"}, text="slow down", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpFetcher(
        client=client,
        allowed_hosts=["fixture"],
        allow_private_hosts=True,
        enforce_robots=False,
    )

    with pytest.raises(FetchError) as error:
        await fetcher.fetch("http://fixture/product/1")

    assert error.value.code == "http_429"
    assert error.value.transient is True
    assert error.value.retry_after == 3
    await client.aclose()


@pytest.mark.asyncio
async def test_fetcher_blocks_oversized_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 128, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpFetcher(
        client=client,
        allowed_hosts=["fixture"],
        allow_private_hosts=True,
        max_response_bytes=64,
        enforce_robots=False,
    )

    with pytest.raises(FetchError, match="byte limit") as error:
        await fetcher.fetch("http://fixture/product/1")

    assert error.value.code == "response_too_large"
    await client.aclose()


@pytest.mark.asyncio
async def test_ssrf_policy_blocks_non_http_and_private_resolution() -> None:
    with pytest.raises(FetchError, match="http/https"):
        await validate_public_url("file:///etc/passwd", allowed_hosts=set(), allow_private_hosts=False)

    with pytest.raises(FetchError) as error:
        await validate_public_url("http://127.0.0.1/admin", allowed_hosts=set(), allow_private_hosts=False)
    assert error.value.code == "private_address"


@pytest.mark.asyncio
async def test_redirect_target_is_validated_before_following() -> None:
    requested_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/admin"}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpFetcher(
        client=client,
        allowed_hosts=["public.example"],
        allow_private_hosts=True,
        enforce_robots=False,
        min_host_interval_seconds=0,
    )

    with pytest.raises(FetchError) as error:
        await fetcher.fetch("http://public.example/start")

    assert error.value.code == "host_not_allowed"
    assert requested_urls == ["http://public.example/start"]
    await client.aclose()


def test_retry_after_parser_handles_seconds_and_invalid_values() -> None:
    assert parse_retry_after("2.5") == 2.5
    assert parse_retry_after("not-a-date") is None
