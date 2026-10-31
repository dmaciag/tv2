from pydantic import BaseModel, ConfigDict, Field, model_validator


class TimeRange(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    range_from: int = Field(..., alias="from", description="Unix seconds")
    range_to: int = Field(..., alias="to", description="Unix seconds")

    @model_validator(mode="after")
    def check_order(self):
        if self.range_to < self.range_from:
            raise ValueError("'to' must not be before 'from'")
        return self


class ChartRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(..., min_length=1, max_length=200, description="Ticker or formula")
    interval: str = Field(..., min_length=1, max_length=8)
