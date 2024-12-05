from fastapi import FastAPI, Depends, HTTPException, Request, Response

from sqlmodel import Session, select
from sqlalchemy import func, desc
from pydantic import ValidationError

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from typing import Annotated, List, Dict
from datetime import datetime
from decimal import Decimal
import uuid, re

from app.database import create_db_and_tables, get_session
from app.models import Claim, ClaimCreate, ClaimPublic

SessionDep = Annotated[Session, Depends(get_session)]

limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# The creation of tables should be done manually when running in production
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.post("/claim-process", response_model=list[ClaimPublic])
def ingest_claim(session: SessionDep, claim_list: List[Dict]):
    def parse_names(field_name: str) -> str:
        '''
        Auxiliary function to normalize inconsistent capitalization for field names
        '''
        parsed_name = re.sub('[^0-9-a-zA-Z]+', ' ', field_name.lower().replace('#', ' number')).replace(' ', '_')
        return parsed_name

    parsed_claim_list = [{parse_names(key):claim[key] for key in claim} for claim in claim_list]

    currency_field_list = ["provider_fees", "allowed_fees", "member_coinsurance", "member_copay"]

    for claim in parsed_claim_list:
        for currency_field in currency_field_list:
            claim[currency_field] = Decimal(claim[currency_field].replace('$', ''))
        claim["net_fee"] = claim["provider_fees"] + claim["member_coinsurance"] + claim["member_copay"] - claim["allowed_fees"]
    
    claim_id = str(uuid.uuid4())    
    try:
        parsed_claim_list = [ClaimCreate(unique_claim_id=claim_id, **claim) for claim in parsed_claim_list]
        parsed_claim_list = [Claim.model_validate(claim) for claim in parsed_claim_list]
    except (ValidationError, ValueError) as e:
        error_details = {
            "errors": [
                {
                    "loc": error["loc"],
                    "type": error["type"],
                    "msg": error["msg"],
                    "input": error["input"],
                }
                for error in e.errors()
            ],
        }
        raise HTTPException(status_code=422, detail=error_details)
    
    for claim in parsed_claim_list:
        session.add(claim)
    session.commit()
    for claim in parsed_claim_list:
        session.refresh(claim)

    return parsed_claim_list

@app.get("/top-providers")
@limiter.limit("10/minute")
def get_top_providers(request: Request, response: Response, session: SessionDep, limit: int = 10):
    top_providers_result = session.exec(
        select(Claim.provider_npi, func.sum(Claim.net_fee).label("total_net_fee"))
        .group_by(Claim.provider_npi)
        .order_by(desc("total_net_fee"))
        .limit(limit)
    ).all()

    top_providers = [{"provider_npi": provider[0], "total_net_fee": Decimal(provider[1])} for provider in top_providers_result]
    return top_providers
