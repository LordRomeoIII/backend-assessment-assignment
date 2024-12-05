import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_session
from app.models import Claim, ClaimCreate
from sqlmodel import SQLModel, Session, create_engine
import os

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "<not defined in environment>")

engine = create_engine(TEST_DATABASE_URL)
client = TestClient(app)

@pytest.fixture(scope="function")
def setup_db():
    """Fixture to set up the database schema."""
    SQLModel.metadata.create_all(bind=engine)
    yield
    # Cleanup can be added here if needed
    # SQLModel.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def session(setup_db):
    """Fixture to provide a database session."""
    with Session(engine) as session:
        yield session

@pytest.fixture(scope="function")
def client(session):
    """Fixture to provide a test client with database session."""
    def override_get_session():
        return session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides[get_session] = get_session

def test_ingest_claim(client):
    claim_data = [
        {
            "service_date": "12/01/23 10:00",
            "submitted_procedure": "D1234",
            "quadrant": "UL",
            "plan_group_number": "P12345",
            "subscriber_number": 56789,
            "provider_npi": 1234567890,
            "provider_fees": "$100.00",
            "allowed_fees": "$80.00",
            "member_coinsurance": "$10.00",
            "member_copay": "$5.00"
        }
    ]
    
    response = client.post("/claim-process", json=claim_data)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["provider_npi"] == "1234567890"

def test_get_top_providers(session, client):
    # Clear database before testing
    session.query(Claim).delete()
    session.commit()

    # Ingest two claims
    client.post("/claim-process", json=[
        {
            "service_date": "12/01/23 10:00",
            "submitted_procedure": "D5678",
            "quadrant": "UR",
            "plan_group_number": "P67890",
            "subscriber_number": 98765,
            "provider_npi": 2345678901,
            "provider_fees": "$150.00",
            "allowed_fees": "$120.00",
            "member_coinsurance": "$15.00",
            "member_copay": "$7.50"
        },
        {
            "service_date": "12/02/23 11:30",
            "submitted_procedure": "D9012",
            "quadrant": "LL",
            "plan_group_number": "P34567",
            "subscriber_number": 34567890,
            "provider_npi": 3456789012,
            "provider_fees": "$200.00",
            "allowed_fees": "$160.00",
            "member_coinsurance": "$20.00",
            "member_copay": "$10.00"
        }
    ])

    response = client.get("/top-providers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 2
    assert response.json()[0]["provider_npi"] == "3456789012" # Higher net fee
    assert response.json()[1]["provider_npi"] == "2345678901" # Lower net fee

def test_validation_error_submitted_procedure(client):
    invalid_data = [
        {
            "service_date": "12/02/23 11:30",
            "submitted_procedure": "F1234",
            "quadrant": "UL",
            "plan_group_number": "P12345",
            "subscriber_number": 56789,
            "provider_npi": 1234567890,
            "provider_fees": "$200.00",
            "allowed_fees": "$160.00",
            "member_coinsurance": "$20.00",
            "member_copay": "$10.00"
        }
    ]
    
    response = client.post("/claim-process", json=invalid_data)
    assert response.status_code == 422
    assert isinstance(response.json(), dict)
    assert "errors" in response.json()['detail']

def test_validation_error_provider_npi(client):
    invalid_data = [
        {
            "service_date": "12/02/23 11:30",
            "submitted_procedure": "D1234",
            "quadrant": "UL",
            "plan_group_number": "P12345",
            "subscriber_number": 56789,
            "provider_npi": 123456789,
            "provider_fees": "$200.00",
            "allowed_fees": "$160.00",
            "member_coinsurance": "$20.00",
            "member_copay": "$10.00"
        }
    ]
    
    response = client.post("/claim-process", json=invalid_data)
    assert response.status_code == 422
    assert isinstance(response.json(), dict)
    assert "errors" in response.json()['detail']

def test_empty_response(client):
    response = client.post("/claim-process", json=[])
    assert response.status_code == 200
    assert len(response.json()) == 0

def test_empty_top_providers(session, client):
    # Clear database before testing
    session.query(Claim).delete()
    session.commit()
    
    response = client.get("/top-providers")
    assert response.status_code == 200
    assert len(response.json()) == 0
