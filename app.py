import os

from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

PROJECT_ID = "healthy-life-495205"

try:
    client = genai.Client(
       vertexai=True,
       project=PROJECT_ID,
       location="us-central1",
    )
except Exception:
    client = genai.Client() # Fallback for non-Vertex environment

# Define the home page route.
@app.route('/', methods=['GET'])
def index():
   '''
   Renders the home page.
   Returns:The rendered template.
   '''
   return render_template('index.html')

@app.route('/plan', methods=['POST'])
def plan():
   '''
   Generates a personalized health plan using Gemini agents.
   '''
   data = request.get_json()
   if not data or 'prompt' not in data:
       return jsonify({"error": "No prompt provided"}), 400

   prompt = data['prompt']

   try:
       from agent import run_health_agents
       result = run_health_agents(prompt)
       return result
   except Exception as e:
       return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
   server_port = int(os.environ.get('PORT', 8080))
   app.run(debug=False, port=server_port, host='0.0.0.0')
