import requests
import json

googlemap_api = "AIzaSyCmEzaGcu2JZorSD9LTYkjt1_0GsxpBMdM"
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
            "center": {"latitude": 40.7128, "longitude": -74.0060}, # NY
            "radius": 5000.0
        }
    }
}

response = requests.post(url, json=payload, headers=headers)
data = response.json()
print(json.dumps(data, indent=2)[:500])
if "places" in data:
    for place in data["places"][:1]:
        print(place.get("displayName", {}).get("text"))
        reviews = place.get("reviews", [])
        for r in reviews[:1]:
            print(r.get("text", {}).get("text", "")[:50])
