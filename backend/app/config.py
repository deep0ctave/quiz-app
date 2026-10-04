from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str = "postgresql+psycopg://localhost:5432/quiz"
    db_username: str = "quiz"
    db_password: str = "quiz"
    jwt_secret: str = Field(default="local-dev-secret-change-me-0123456789abcdef", min_length=32)
    jwt_issuer: str = "schoolmela-quiz"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    bootstrap_admin_name: str = "Admin"
    bootstrap_admin_mobile: str = "9999999999"
    bootstrap_admin_pin: str = "123456"
    swagger_enabled: bool = True

    @property
    def sqlalchemy_url(self) -> str:
        return make_url(self.db_url).set(username=self.db_username, password=self.db_password).render_as_string(
            hide_password=False
        )


settings = Settings()