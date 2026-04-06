from main import app
from fastapi.routing import APIRoute

def print_routes():
    print("Registered Routes:")
    for route in app.routes:
        if isinstance(route, APIRoute):
            print(f"{route.methods} {route.path}")

if __name__ == "__main__":
    print_routes()
