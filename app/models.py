from sqlmodel import SQLModel, Field
from pydantic import field_validator, validator

from datetime import datetime
from decimal import Decimal

# Base Model
class ClaimBase(SQLModel):
    service_date: datetime = Field()
    submitted_procedure: str = Field(index=True)
    quadrant: str | None = Field()
    plan_group_number: str = Field(index=True)
    subscriber_number: str = Field(index=True)
    provider_npi: str = Field(index=True)
    provider_fees: Decimal = Field(decimal_places=2)
    allowed_fees: Decimal = Field(decimal_places=2)
    member_coinsurance: Decimal = Field(decimal_places=2)
    member_copay: Decimal = Field(decimal_places=2)

# DB Model
class Claim(ClaimBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    unique_claim_id: str = Field(index=True)
    net_fee: Decimal = Field(decimal_places=2)

# Public Model
class ClaimPublic(ClaimBase):
    id: int
    unique_claim_id: str
    net_fee: Decimal

# Create Model
class ClaimCreate(ClaimBase):
    unique_claim_id: str
    net_fee: Decimal

    class Config:
        validate_assignment = True

    @field_validator('service_date', mode='before')
    def convert_service_date(cls, value):
        if isinstance(value, str):
            return datetime.strptime(value, '%m/%d/%y %H:%M')
        raise ValueError("Service date must be a valid date")
    
    @field_validator('subscriber_number', mode='before')
    def convert_subscriber_number(cls, value):
        if isinstance(value, int):
            return str(value)
        raise ValueError("Subscriber number must be a number")
    
    @field_validator('provider_npi', mode='before')
    def validate_and_convert_provider_npi(cls, value):
        if isinstance(value, int):
            str_value = str(value)
            if len(str_value) != 10:
                raise ValueError("Provider NPI must be a 10 digit number")
            return str(value)
        raise ValueError("Provider NPI must be a number")
    
    @field_validator('submitted_procedure')
    def validate_submitted_procedure(cls, value):
        if not value.startswith('D'):
            raise ValueError("Submitted procedure must start with 'D'")
        return value
