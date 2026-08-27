from catalog_forge.config import Settings


def test_comma_separated_host_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("CATALOG_FORGE_ALLOWED_HOSTS", "books.toscrape.com,fixture")
    monkeypatch.setenv("CATALOG_FORGE_PRIVATE_HOST_ALLOWLIST", "fixture")

    settings = Settings()

    assert settings.allowed_hosts == ["books.toscrape.com", "fixture"]
    assert settings.private_host_allowlist == ["fixture"]
