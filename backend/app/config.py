from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_anon_key: str
    # Server-only secret: signs photo upload URLs and checks uploads exist (ADR 0009). Never
    # send it to the frontend or log it.
    supabase_service_role_key: str
    environment: str = "development"
    frontend_origin: str = ""
    frontend_preview_origin_regex: str = r"^https://renest-[a-z0-9-]+\.vercel\.app$"

    # extra="ignore": skip keys this class doesn't define (e.g. local-only TEST_EMAIL /
    # TEST_PASSWORD used by dev scripts) instead of refusing to start. Required settings are
    # still required.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
