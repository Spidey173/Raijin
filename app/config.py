import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

class Settings(BaseSettings):
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_DB: str = Field(default="raijin")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    UPLOAD_DIR: str = Field(default=os.path.join(os.getcwd(), "uploads"))
    MAX_UPLOAD_SIZE_BYTES: int = Field(default=50 * 1024 * 1024)  # 50 MB

    @field_validator("UPLOAD_DIR", mode="after")
    @classmethod
    def validate_upload_dir(cls, v: str) -> str:
        try:
            os.makedirs(v, exist_ok=True)
            test_file = os.path.join(v, ".write_test")
            with open(test_file, "w") as f:
                f.write("")
            os.remove(test_file)
            return v
        except (PermissionError, OSError):
            local_dir = os.path.join(os.getcwd(), "uploads")
            os.makedirs(local_dir, exist_ok=True)
            return local_dir
    
    # LLM Multi-Provider Settings
    LLM_PROVIDER: str = Field(default="auto")  # 'auto', 'groq', 'google', 'anthropic', 'openai'
    
    # Groq (Default model: qwen/qwen3.8-27b)
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = Field(default="qwen/qwen3.8-27b")
    
    # Google Gemini
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash")
    
    # Anthropic Claude
    ANTHROPIC_API_KEY: str = Field(default="")
    ANTHROPIC_MODEL: str = Field(default="claude-3-5-haiku-20241022")
    
    # OpenAI
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    
    # Allowed CORS Origins
    CORS_ORIGINS: str = Field(default="*")
    
    # Cryptographic Authentication & Security
    SECRET_KEY: str = Field(default="raijin-production-secure-jwt-secret-key-32-chars")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24)  # 24 hours
    API_KEY: str = Field(default="")  # Optional service-to-service master API key
    ENABLE_ANONYMOUS_DEV_MODE: bool = Field(default=False)  # Allows default-user only when explicitly enabled

    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
