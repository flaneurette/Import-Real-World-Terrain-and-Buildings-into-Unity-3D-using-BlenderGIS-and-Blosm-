/*

import requests
import math
import json
from xml.etree import ElementTree as ET

# ----------------------------
# Convert lat/lon to local XY (Unity-friendly)
def latlon_to_xy(lat, lon, origin_lat, origin_lon):
	R = 6371000  # Earth radius in meters
	x = math.radians(lon - origin_lon) * R * math.cos(math.radians(origin_lat))
	z = math.radians(lat - origin_lat) * R
	return x, z
# ----------------------------

# Bounding box: (south, west, north, east)
bbox = (52.0, 4.0, 52.05, 4.05)  # change to your area
origin_lat, origin_lon = bbox[0], bbox[1]

# Overpass QL query — all your props
query = f"""
(
  node["highway"="street_lamp"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["amenity"="bench"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["highway"="traffic_sign"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["traffic_calming"="bump"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["amenity"="post_box"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["amenity"="trash_can"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["emergency"="fire_hydrant"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["natural"="tree"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
out body;
"""

print("Fetching Overpass data…")

url = "https://overpass-api.de/api/interpreter"
response = requests.post(url, data={"data": query})
response.raise_for_status()

root = ET.fromstring(response.text)
props = []

# ----------------------------
# Parse XML result
for node in root.findall("node"):
	lat = float(node.attrib["lat"])
	lon = float(node.attrib["lon"])
	x, z = latlon_to_xy(lat, lon, origin_lat, origin_lon)

	tags = {tag.attrib["k"]: tag.attrib["v"] for tag in node.findall("tag")}
	obj_type = None

	if tags.get("highway") == "street_lamp":
		obj_type = "streetlight"
	elif tags.get("amenity") == "bench":
		obj_type = "bench"
	elif tags.get("highway") == "traffic_sign":
		obj_type = "traffic_sign"
	elif tags.get("traffic_calming") == "bump":
		obj_type = "speed_bump"
	elif tags.get("amenity") == "post_box":
		obj_type = "post_box"
	elif tags.get("amenity") == "trash_can":
		obj_type = "trash_can"
	elif tags.get("emergency") == "fire_hydrant":
		obj_type = "fire_hydrant"
	elif tags.get("natural") == "tree":
		obj_type = "tree"

	if obj_type:
		props.append({
			"type": obj_type,
			"x": x,
			"z": z,
			"lat": lat,
			"lon": lon,
			"tags": tags
		})

# ----------------------------
# Export to JSON
with open("city_props.json", "w", encoding="utf-8") as f:
	json.dump(props, f, indent=2)

print(f"✅ Exported {len(props)} props to city_props.json")



*/




OR WITH PYTHON MODULE:
    
    
    
import overpy
import math
import json

# ----------------------------
# Helper: Convert lat/lon to Unity local coordinates
def latlon_to_xy(lat, lon, origin_lat, origin_lon):
    R = 6371000  # Earth radius in meters
    x = math.radians(lon - origin_lon) * R * math.cos(math.radians(origin_lat))
    z = math.radians(lat - origin_lat) * R  # Unity Z-axis
    return x, z
# ----------------------------

api = overpy.Overpass()

# Bounding box (south, west, north, east)
bbox = (52.0, 4.0, 52.05, 4.05)
origin_lat, origin_lon = bbox[0], bbox[1]

# Overpass QL query for props (everything except what BLOSM handles)
query = f"""
(
  node["highway"="street_lamp"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["amenity"="bench"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["highway"="traffic_sign"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["traffic_calming"="bump"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["amenity"="post_box"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["amenity"="trash_can"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["emergency"="fire_hydrant"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
  node["natural"="tree"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
);
out body;
"""

print("Fetching Overpass data…")
result = api.query(query)
print(f"Fetched {len(result.nodes)} nodes")

# ----------------------------
# Initialize dictionary for each type
props_dict = {
    "streetlights": [],
    "benches": [],
    "traffic_signs": [],
    "speed_bumps": [],
    "mailboxes": [],
    "trash_cans": [],
    "fire_hydrants": [],
    "trees": []
}

# Process nodes
for node in result.nodes:
    x, z = latlon_to_xy(node.lat, node.lon, origin_lat, origin_lon)

    if node.tags.get("highway") == "street_lamp":
        props_dict["streetlights"].append({"x": x, "z": z, "lat": node.lat, "lon": node.lon, "tags": node.tags})
    elif node.tags.get("amenity") == "bench":
        props_dict["benches"].append({"x": x, "z": z, "lat": node.lat, "lon": node.lon, "tags": node.tags})
    elif node.tags.get("highway") == "traffic_sign":
        props_dict["traffic_signs"].append({"x": x, "z": z, "lat": node.lat, "lon": node.lon, "tags": node.tags})
    elif node.tags.get("traffic_calming") == "bump":
        props_dict["speed_bumps"].append({"x": x, "z": z, "lat": node.lat, "lon": node.lon, "tags": node.tags})
    elif node.tags.get("amenity") == "post_box":
        props_dict["mailboxes"].append({"x": x, "z": z, "lat": node.lat, "lon": node.lon, "tags": node.tags})
    elif node.tags.get("amenity") == "trash_can":
        props_dict["trash_cans"].append({"x": x, "z": z, "lat": node.lat, "lon": node.lon, "tags": node.tags})
    elif node.tags.get("emergency") == "fire_hydrant":
        props_dict["fire_hydrants"].append({"x": x, "z": z, "lat": node.lat, "lon": node.lon, "tags": node.tags})
    elif node.tags.get("natural") == "tree":
        props_dict["trees"].append({"x": x, "z": z, "lat": node.lat, "lon": node.lon, "tags": node.tags})

# ----------------------------
# Export JSON
with open("city_props_layers.json", "w") as f:
    json.dump(props_dict, f, indent=2)

# ----------------------------
# Summary
for k, v in props_dict.items():
    print(f"{k}: {len(v)} objects")
