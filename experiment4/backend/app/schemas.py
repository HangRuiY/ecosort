from __future__ import annotations

from pydantic import BaseModel, Field


class TextQuery(BaseModel):
    text: str = Field(..., description="物品描述，1-300 字", examples=["沾了油的外卖塑料餐盒"])
    region: str = Field("general", description="规则地区：general / shanghai")


class ApiResponse(BaseModel):
    code: int = Field(..., examples=[200])
    result: dict | list | None = None
    msg: str = Field(..., examples=["ok"])
