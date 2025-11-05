import os
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Check if the API key is loaded
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ GOOGLE_API_KEY not found in .env")
    exit(1)

# Initialize client with your API key
client = genai.Client(api_key=api_key)

# List all available Gemini models
print("\n✅ Available Gemini models:\n")
for model in client.models.list():
    print("-", model.name)
