import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SOCKET_URL = os.getenv("SOCKET_URL")