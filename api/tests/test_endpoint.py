import requests
import time

def test_endpoint():
    base_url = "http://127.0.0.1:7860"
    
    endpoints = [
        "/api/admin/config/models",
        "/api/admin/config/email",
        "/api/admin/users"
    ]

    for ep in endpoints:
        url = f"{base_url}{ep}"
        print(f"Testing URL: {url}")
        try:
            response = requests.get(url)
            print(f"Status Code: {response.status_code}")
        except Exception as e:
            print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_endpoint()
