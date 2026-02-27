"""Pydantic v2 schema models for keyword library (keywords.yaml)."""

from pydantic import BaseModel, Field


class KeywordCategory(BaseModel):
    active: bool
    keywords: list[str]


class KeywordsConfig(BaseModel):
    categories: dict[str, KeywordCategory]
    exclusions: list[str] = Field(default_factory=list)

    def active_keywords(self) -> list[str]:
        """Return all keywords from active categories only."""
        result: list[str] = []
        for cat in self.categories.values():
            if cat.active:
                result.extend(cat.keywords)
        return result

    def active_categories(self) -> dict[str, KeywordCategory]:
        """Return only active categories."""
        return {name: cat for name, cat in self.categories.items() if cat.active}
