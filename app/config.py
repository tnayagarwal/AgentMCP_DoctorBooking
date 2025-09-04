from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
	app_env: str = Field(default="development")
	database_url: str = Field(default="sqlite:///./clinic.db")
	timezone: str = Field(default="UTC")

	groq_api_key: str | None = None
	groq_model: str = Field(default="llama3-8b-8192")

	google_token_file: str | None = Field(default="token.json")

	whatsapp_token: str | None = None
	whatsapp_phone_id: str | None = None
	whatsapp_to: str | None = None
	whatsapp_template: str = Field(default="hello_world")
	whatsapp_lang: str = Field(default="en_US")

	celery_broker_url: str = Field(default="redis://localhost:6379/0")
	celery_result_backend: str = Field(default="redis://localhost:6379/1")

	class Config:
		env_file = ".env"
		env_file_encoding = "utf-8"

settings = Settings()
