# list_models.py
import google.generativeai as genai
import os
import sys

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("ERROR: GOOGLE_API_KEY not set. Set it before running this script.")
    print("PowerShell temporary (current session): $env:GOOGLE_API_KEY=\"your_key_here\"")
    print("PowerShell permanent: setx GOOGLE_API_KEY \"your_key_here\"   (then re-open shell)")
    sys.exit(1)

genai.configure(api_key=API_KEY)

print("=== Available Models for this API Key ===")
print("Model Name".ljust(50), "| Supported Methods")
print("-" * 80)

for m in genai.list_models():
    methods = ", ".join(m.supported_generation_methods)
    print(m.name.ljust(50), "|", methods)

print("\nRecommended default for this flask app: models/gemini-flash-latest")
print("You can override the model used by the app with the GENAI_MODEL environment variable.")
