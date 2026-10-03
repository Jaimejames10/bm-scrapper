from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SearchRequest(BaseModel):
    account_code: str | None = Field(default=None, max_length=30)
    identity_document: str | None = Field(default=None, max_length=30)

    @field_validator("account_code", "identity_document", mode="before")
    @classmethod
    def normalize_filter(cls, value: object) -> object:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @model_validator(mode="after")
    def require_at_least_one_filter(self) -> "SearchRequest":
        if not self.account_code and not self.identity_document:
            raise ValueError("Ingresa el código de cuenta o el documento de identidad")
        return self


class UserDetails(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str
    account_code: str
    contract_number: str
    contract_date: str
    full_name: str = ""


class SearchResponse(BaseModel):
    query: str
    results: list[UserDetails]
