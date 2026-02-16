import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

try:
    api_key = os.getenv("OPENAI_API_KEY")
    print(f"API Key found: {api_key[:5]}... (length: {len(api_key)})")
    
    client = OpenAI(api_key=api_key)
    print("Client initialized.")
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("Response received:")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
