from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .reliability import CircuitRegistry


class FetchError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        transient: bool,
        retry_after: float | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.transient = transient
        self.retry_after = retry_after
        self.status_code = status_code


@dataclass(slots=True)
class FetchResult:
    url: str
    final_url: str
    status_code: int
    text: str
    latency_ms: float
    bytes_received: int
    content_type: str


class HostLimiter:
    def __init__(self, max_concurrency: int, min_interval_seconds: float):
        self.max_concurrency = max_concurrency
        self.min_interval_seconds = min_interval_seconds
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}

    async def __aenter_host__(self, host: str) -> None:
        semaphore = self._semaphores.setdefault(host, asyncio.Semaphore(self.max_concurrency))
        await semaphore.acquire()
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            elapsed = time.monotonic() - self._last_request.get(host, 0.0)
            if elapsed < self.min_interval_seconds:
                await asyncio.sleep(self.min_interval_seconds - elapsed)
            self._last_request[host] = time.monotonic()

    def release(self, host: str) -> None:
        self._semaphores[host].release()


class RobotsPolicy:
    def __init__(self, client: httpx.AsyncClient, user_agent: str):
        self.client = client
        self.user_agent = user_agent
        self._cache: dict[str, RobotFileParser] = {}

    async def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._cache:
            parser = RobotFileParser()
            robots_url = f"{origin}/robots.txt"
            try:
                response = await self.client.get(robots_url, timeout=5.0)
                if response.status_code >= 500:
                    raise FetchError("robots_unavailable", f"robots.txt returned {response.status_code}", transient=True)
                parser.parse(response.text.splitlines() if response.status_code == 200 else [])
            except httpx.HTTPError as exc:
                raise FetchError("robots_unavailable", str(exc), transient=True) from exc
            self._cache[origin] = parser
        return self._cache[origin].can_fetch(self.user_agent, url)


class HttpFetcher:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        allowed_hosts: list[str] | None = None,
        private_host_allowlist: list[str] | None = None,
        allow_private_hosts: bool = False,
        max_concurrency_per_host: int = 8,
        min_host_interval_seconds: float = 0.1,
        max_response_bytes: int = 5_000_000,
        user_agent: str = "CatalogForge/0.1 (+https://github.com/zodia8393/catalog-forge)",
        enforce_robots: bool = True,
    ):
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            follow_redirects=False,
            headers={"User-Agent": user_agent},
            timeout=httpx.Timeout(15.0),
        )
        self.allowed_hosts = {host.lower() for host in (allowed_hosts or [])}
        self.private_host_allowlist = {host.lower() for host in (private_host_allowlist or [])}
        self.allow_private_hosts = allow_private_hosts
        self.max_response_bytes = max_response_bytes
        self.user_agent = user_agent
        self.enforce_robots = enforce_robots
        self.limiter = HostLimiter(max_concurrency_per_host, min_host_interval_seconds)
        self.circuits = CircuitRegistry()
        self.robots = RobotsPolicy(self.client, user_agent)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def render(self, url: str, timeout_seconds: float = 20.0) -> str:
        return await render_with_playwright(
            url,
            timeout_seconds=timeout_seconds,
            allowed_hosts=self.allowed_hosts,
            allow_private_hosts=self.allow_private_hosts,
            private_host_allowlist=self.private_host_allowlist,
        )

    async def fetch(self, url: str) -> FetchResult:
        original_url = url
        current_url = url
        started = time.perf_counter()
        max_redirects = 5

        for _ in range(max_redirects + 1):
            parsed = await validate_public_url(
                current_url,
                allowed_hosts=self.allowed_hosts,
                allow_private_hosts=self.allow_private_hosts,
                private_host_allowlist=self.private_host_allowlist,
            )
            host = parsed.hostname or ""
            breaker = self.circuits.for_host(host)
            if not breaker.allow_request():
                raise FetchError("circuit_open", f"circuit is open for {host}", transient=True)
            if self.enforce_robots and not await self.robots.allowed(current_url):
                raise FetchError("robots_disallowed", f"robots.txt disallows {current_url}", transient=False)

            await self.limiter.__aenter_host__(host)
            try:
                async with self.client.stream("GET", current_url, follow_redirects=False) as response:
                    if 300 <= response.status_code < 400:
                        location = response.headers.get("Location")
                        if not location:
                            raise FetchError(
                                "invalid_redirect",
                                f"upstream returned {response.status_code} without Location",
                                transient=False,
                            )
                        breaker.record_success()
                        current_url = urljoin(current_url, location)
                        continue

                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self.max_response_bytes:
                            breaker.record_failure()
                            raise FetchError(
                                "response_too_large",
                                "response exceeded configured byte limit",
                                transient=False,
                            )
                    latency_ms = (time.perf_counter() - started) * 1000
                    retry_after = parse_retry_after(response.headers.get("Retry-After"))
                    if response.status_code == 429 or response.status_code >= 500:
                        breaker.record_failure()
                        raise FetchError(
                            f"http_{response.status_code}",
                            f"upstream returned {response.status_code}",
                            transient=True,
                            retry_after=retry_after,
                            status_code=response.status_code,
                        )
                    if response.status_code >= 400:
                        raise FetchError(
                            f"http_{response.status_code}",
                            f"upstream returned {response.status_code}",
                            transient=False,
                            status_code=response.status_code,
                        )
                    breaker.record_success()
                    encoding = response.encoding or "utf-8"
                    return FetchResult(
                        url=original_url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        text=bytes(body).decode(encoding, errors="replace"),
                        latency_ms=latency_ms,
                        bytes_received=len(body),
                        content_type=response.headers.get("content-type", ""),
                    )
            except httpx.TimeoutException as exc:
                breaker.record_failure()
                raise FetchError("timeout", str(exc), transient=True) from exc
            except httpx.TransportError as exc:
                breaker.record_failure()
                raise FetchError("transport_error", str(exc), transient=True) from exc
            finally:
                self.limiter.release(host)

        raise FetchError("too_many_redirects", f"redirect limit exceeded for {original_url}", transient=False)


async def validate_public_url(
    url: str,
    *,
    allowed_hosts: set[str],
    allow_private_hosts: bool,
    private_host_allowlist: set[str] | None = None,
) -> object:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise FetchError("invalid_url", "only absolute http/https URLs are accepted", transient=False)
    host = parsed.hostname.lower()
    if allowed_hosts and host not in allowed_hosts:
        raise FetchError("host_not_allowed", f"host {host} is not allowlisted", transient=False)
    if allow_private_hosts or host in (private_host_allowlist or set()):
        return parsed
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        if not literal_ip.is_global:
            raise FetchError("private_address", f"host resolves to non-public address {literal_ip}", transient=False)
        return parsed
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError("dns_error", str(exc), transient=True) from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise FetchError("private_address", f"host resolves to non-public address {ip}", transient=False)
    return parsed


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        try:
            return max((parsedate_to_datetime(value).timestamp() - time.time()), 0.0)
        except (TypeError, ValueError, OverflowError):
            return None


async def render_with_playwright(
    url: str,
    timeout_seconds: float = 20.0,
    *,
    allowed_hosts: set[str] | None = None,
    allow_private_hosts: bool = False,
    private_host_allowlist: set[str] | None = None,
) -> str:
    allowed_hosts = allowed_hosts or set()
    private_host_allowlist = private_host_allowlist or set()
    await validate_public_url(
        url,
        allowed_hosts=allowed_hosts,
        allow_private_hosts=allow_private_hosts,
        private_host_allowlist=private_host_allowlist,
    )
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise FetchError("browser_unavailable", "install catalog-forge[browser]", transient=False) from exc
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            validated_hosts: set[str] = set()

            async def guard_request(route: object) -> None:
                request_url = route.request.url
                parsed = urlparse(request_url)
                if parsed.scheme not in {"http", "https"}:
                    await route.continue_()
                    return
                host = (parsed.hostname or "").lower()
                try:
                    if host not in validated_hosts:
                        await validate_public_url(
                            request_url,
                            allowed_hosts=allowed_hosts,
                            allow_private_hosts=allow_private_hosts,
                            private_host_allowlist=private_host_allowlist,
                        )
                        validated_hosts.add(host)
                    await route.continue_()
                except FetchError:
                    await route.abort("blockedbyclient")

            await page.route("**/*", guard_request)
            try:
                await page.goto(url, wait_until="networkidle", timeout=int(timeout_seconds * 1000))
                return await page.content()
            except PlaywrightError as exc:
                raise FetchError("browser_error", str(exc), transient=True) from exc
        finally:
            await browser.close()
