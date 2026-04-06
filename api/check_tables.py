from sqlalchemy import create_engine, inspect, text
from config import settings

def check_tables():
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    
    columns = inspector.get_columns("email_config")
    print("Email Config Columns:")
    for col in columns:
        print(f"- {col['name']} ({col['type']})")

if __name__ == "__main__":
    check_tables()
