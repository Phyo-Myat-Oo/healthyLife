import os
import json
from google import genai
from google.genai import types

import googlemaps
import requests

# Use your existing API key variable
googlemap_api = "AIzaSyCmEzaGcu2JZorSD9LTYkjt1_0GsxpBMdM"
maps_client = googlemaps.Client(key=googlemap_api)



PROJECT_ID = "healthy-life-495205"

try:
    client = genai.Client(
       vertexai=True,
       project=PROJECT_ID,
       location="us-central1",
    )
except Exception:
    client = genai.Client()


def get_gym_recommendations_new(location_query: str):
    """
    Fetches real-time gym data using the Places API (New).
    """
    try:
        # 1. Geocoding
        geo = maps_client.geocode(location_query)
        if not geo: return "Location not found."
        lat = geo[0]['geometry']['location']['lat']
        lng = geo[0]['geometry']['location']['lng']

        # 2. Places API (New) Call
        url = "https://places.googleapis.com/v1/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": googlemap_api,
            "X-Goog-FieldMask": "places.displayName,places.rating,places.formattedAddress,places.userRatingCount,places.reviews"
        }
        payload = {
            "includedTypes": ["gym"],
            "maxResultCount": 10,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": 5000.0
                }
            }
        }

        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        # 3. Parsing
        results = []
        if "places" in data:
            for place in data["places"]:
                name = place.get("displayName", {}).get("text", "Unknown Gym")
                rating = place.get("rating", "N/A")
                address = place.get("formattedAddress", "No address")
                reviews = place.get("reviews", [])
                review_texts = []
                for r in reviews[:2]:
                    text = r.get("text", {}).get("text", "").replace('\n', ' ')
                    if text: review_texts.append(text[:150] + "...")
                review_str = " | ".join(review_texts) if review_texts else "No reviews available"
                results.append(f"• {name} (Rating: {rating}) - {address}\n  Reviews: {review_str}")
        
        return "\n".join(results) if results else "No gyms found nearby."
    except Exception as e:
        return f"Error fetching gyms: {str(e)}"



def run_health_agents(user_profile: str) -> str:
    """
    Executes a multi-step agent workflow to generate a personalized health plan.
    This simulates the behavior of multiple specialized agents working together.
    """
    print("🚀 Starting Agent Workflow...")
    
    # 1. Medical Agent
    print("   -> Running Medical Agent...")
    medical_prompt = f"""
    Act as a Clinical Nutrition & Fitness Architect. Take the following personal data and transform it into a standardized constraints block.
    Calculate TDEE and Macros, map sleep schedule, identify restricted exercises.
    
    User Profile / Request:
    {user_profile}
    
    Output a structured summary of constraints.
    """
    medical_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=medical_prompt
    ).text

    # 2. Workout Planner Agent
    print("   -> Running Workout Planner Agent...")
    workout_prompt = f"""
    You are an expert Certified Strength and Conditioning Specialist.
    Based on the following constraints, create a safe, effective workout plan.
    
    Constraints:
    {medical_response}
    
    Provide 3-5 bullet points using • character. Focus strictly on exercises and sets/reps.
    """
    workout_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=workout_prompt
    ).text

    # 3. Diet/Meal Planner Agent
    print("   -> Running Diet & Nutrition Agent...")
    diet_prompt = f"""
    You are an expert nutritionist.
    Based on the following constraints, create a structured diet plan to hit the macros perfectly.
    
    Constraints:
    {medical_response}
    
    Provide 3-5 bullet points using • character detailing meals, portions, and timings.
    """
    diet_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=diet_prompt
    ).text
    
  # 4. Integrated Gym / Location Agent
    print("   -> Running Gym Selection Agent...")
    
    # Logic to check if we should call the Maps API
    # You can make this smarter by using a small LLM call to extract the location
    location_keywords = ["near", "in", "at", "around"]
    has_location = any(word in user_profile.lower() for word in location_keywords)
    
    if has_location:
        print("      [Real-time Search Triggered]")
        # We pass the user_profile to the tool logic
        gym_details = get_gym_recommendations_new(user_profile)
        gym_prompt = f"""
        You are an expert fitness advisor. The user is looking for a gym.
        User Profile: {user_profile}
        
        Here are up to 10 nearby gyms with their ratings and reviews:
        {gym_details}
        
        Based on the user's profile and the gym details, recommend the best gym for them and explain why. Provide a summary of the recommendation and list a few runner-ups.
        """
        gym_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=gym_prompt
        ).text
    else:
        # Fallback to general advice
        gym_prompt = f"Suggest general gym setup for: {user_profile}. Provide 2-3 bullet points."
        gym_response = client.models.generate_content(
            model="gemini-2.5-flash", # Use 2.0-flash for speed
            contents=gym_prompt
        ).text

    # 5. Final Formatting Agent (Using gym_response from above)
    print("   -> Running Formatting Agent...")
    final_prompt = f"""
    Format into a JSON object.
    Medical: {medical_response}
    Workout: {workout_response}
    Diet: {diet_response}
    Gym/Location: {gym_response}
    
    JSON Keys: "diet", "workout", "wellness", "gym" (use the Gym/Location data here).
    """
    
    final_response_obj = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=final_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    final_response = final_response_obj.text
    
    return final_response