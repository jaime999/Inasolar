from fastapi.testclient import TestClient
from main import app
import dotenv

client = TestClient(app)
API_KEY = dotenv.dotenv_values()["API_KEY"]
API_ENDPOINTS = [
    "/api/similardays/getTargetDateData",
    "/api/similardays/getMarginsPondersInfo",
    "/api/similardays/getMarginsGraphicsData",
    "/api/similardays/getPondersGraphicsData"
]

def test_missing_auth():
    for endpoint in API_ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 422

def test_auth():
    for endpoint in API_ENDPOINTS:
        response = client.get(f"{endpoint}?apikey=random")
        assert response.status_code == 401
        response = client.get(f"{endpoint}?apikey={API_KEY}")
        assert response.status_code != 401

def test_missing_data():
    test_cases = [
        {"target_date": "2022-03-01T00:00:00"},
        {"target_date": "2022-03-04T00:00:00"},
        {"target_date": "1900-03-04T00:00:00"},
        {"target_date": "99999-03-04T00:00:00"},
        {"target_date": "0000-03-04T00:00:00"},
        {"target_date": "2022-03-05T00:00:00"}
    ]
    for endpoint in API_ENDPOINTS[-len(API_ENDPOINTS)+2:1]:
        for test_case in test_cases:
            params = "&".join([f"{key}={value}" for key, value in test_case.items()])
            response = client.get(f"{endpoint}?apikey={API_KEY}&{params}&location=1")
            if test_case["target_date"] == "99999-03-04T00:00:00":
                assert response.status_code == 422
            elif test_case["target_date"] == "2022-03-05T00:00:00":
                assert response.status_code == 200
            else:
                print(endpoint,test_case)
                assert response.status_code == 404


def test_margin_graphic_data():
    test_cases = [
        {"target_date": "2022-01-01T00:00:00"},
        {"target_date": "2022-04-01T00:00:00"},
        {"target_date": "2022-03-01T00:00:00"},
        {"target_date": "2022-03-04T00:00:00"}
    ]
    for test_case in test_cases:
        params = "&".join([f"{key}={value}" for key, value in test_case.items()])
        response = client.get(f"/api/similardays/getMarginsGraphicsData?apikey={API_KEY}&{params}")
        data = response.json()
        if test_case["target_date"] == "2022-01-01T00:00:00":
            assert len(data["data"]) == 24
        if test_case["target_date"] == "2022-04-01T00:00:00":
            assert len(data["data"]) == 3
        if test_case["target_date"] == "2022-03-01T00:00:00" or test_case["target_date"] == "2022-03-04T00:00:00" :
            assert response.status_code == 404
