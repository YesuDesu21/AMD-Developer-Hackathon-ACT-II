import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

'''
This is just to test how the firework api works

- Jasper
'''

# =====================================================================
# 1. ENVIRONMENT & PATH SETTINGS (SMART AUTOMATIC SEARCH)
# =====================================================================
current_file = Path(__file__).resolve()

# Look for the .env file dynamically by walking upwards through parent directories
env_path = None
for parent in current_file.parents:
    possible_env = parent / '.env'
    if possible_env.exists():
        env_path = possible_env
        break

if env_path:
    print(f" Found .env file at: {env_path}")
    load_dotenv(dotenv_path=env_path)
else:
    print(" ERROR: Could not find any .env file in any parent directory!")
    exit(1)

# Extract your API key safely
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")

if not FIREWORKS_API_KEY:
    print(" ERROR: FIREWORKS_API_KEY is empty or missing within the located .env file!")
    exit(1)

# =====================================================================
# 2. FIREWORKS API CONFIGURATION
# =====================================================================
# Endpoint URL for standard serverless generation
url = "https://api.fireworks.ai/inference/v1/chat/completions"

# Set up headers with your bearer token authorization
headers = {
    "Authorization": f"Bearer {FIREWORKS_API_KEY}",
    "Content-Type": "application/json"
}


model_string = "accounts/fireworks/models/deepseek-v4-pro"

# The raw execution payload
payload = {
    "model": model_string,
    "messages": [
        {
            "role": "user", 
            "content": "Respond with exactly the word: SUCCESS"
        }
    ],
    "max_tokens": 10,
    "temperature": 0.0  # Determinstic for testing
}

# =====================================================================
# 3. NETWORK EXECUTION & TOKEN LOGGING
# =====================================================================
print(f"Connecting to Fireworks AI using {model_string}...")

try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    
    # Check if the HTTP status code is a green pass (200 OK)
    if response.status_code == 200:
        response_data = response.json()
        
        # Parse the structured response components
        ai_answer = response_data['choices'][0]['message']['content'].strip()
        usage_stats = response_data.get('usage', {})
        
        print("\n=============================================")
        print(" CONNECTION SUCCESSFUL!")
        print("=============================================")
        print(f"Model Output:     {ai_answer}")
        print(f"Prompt Tokens:    {usage_stats.get('prompt_tokens', 0)}")
        print(f"Response Tokens:  {usage_stats.get('completion_tokens', 0)}")
        print(f"Total Scored:     {usage_stats.get('total_tokens', 0)}")
        print("=============================================")
        
    else:
        print(f"\n API CONNECTION REJECTED (Status Code: {response.status_code})")
        print("Error Response Body:")
        print(response.text)

except requests.exceptions.Timeout:
    print("\n NETWORK TIMEOUT: The connection took longer than 10 seconds.")
except Exception as e:
    print(f"\n UNEXPECTED SYSTEM ERROR: {e}")