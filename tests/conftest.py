import os

# Тестовые заглушки, не секреты — нужны, чтобы app.config.Settings() успешно
# сконструировался при импорте до того, как тесты успеют что-либо замокать.
os.environ.setdefault("BOT_TOKEN", "000000:test-token-for-unit-tests")
os.environ.setdefault("CRM_ENDPOINT_URL", "https://example.test/v1/leads")
