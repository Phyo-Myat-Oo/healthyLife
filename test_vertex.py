from google import genai
try:
    client = genai.Client(vertexai=True, project="healthy-life-495205", location="us-central1")
    print(client.models.generate_content(model="gemini-2.5-flash", contents="Say hi").text)
except Exception as e:
    print(f"Error: {e}")
