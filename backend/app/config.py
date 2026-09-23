from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_anon_key: str
    environment: str = "development"
    frontend_origin: str = ""
    frontend_preview_origin_regex: str = r"^https://renest-[a-z0-9-]+\.vercel\.app$"

    class Config:
        env_file = ".env"

settings = Settings()
