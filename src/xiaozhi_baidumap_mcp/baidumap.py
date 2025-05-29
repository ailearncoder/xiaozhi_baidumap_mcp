# server.py
import logging
from typing import Optional, Dict, Any, Literal
from urllib.parse import urlencode # For correct query string encoding
import re # Added for validation regex

from pydantic import Field
from typing_extensions import Annotated # For older Python versions, ensure typing_extensions is installed if needed. For Python 3.9+ use typing.Annotated

from mcp.server.fastmcp import FastMCP
# Assuming these are your custom classes, ensure they are correctly defined/imported
from xiaozhi_app.plugins import AndroidDevice, Intent, Uri
import os

# --- Configuration ---
DEFAULT_SRC = "andr.xiaomi.assistant" # Your app identifier
BAIDUMAP_NATIVE_BASE_URL = "baidumap://map/"

# Create an MCP server
mcp = FastMCP(
    "BaiduMapsHelper",
    # Default is "warn", you can change to "error", "replace", or "ignore"
    on_duplicate_tools="warn"
)

def init_log():
    logger_name = 'baidu_maps_mcp'
    logger = logging.getLogger(logger_name)
    if logger.hasHandlers(): # Avoid adding handlers multiple times
        logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    log_file_path = 'baidu_maps_mcp.log'
    file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger

logger = init_log()

# --- Navigation and URI Building ---
def Navigate(uri: str) -> Dict[str, Any]:
    """
    Attempts to open the given URI an Android device.
    Returns a dictionary indicating success or failure.
    """
    try:
        device = AndroidDevice()
        intent = Intent(Intent.ACTION_VIEW)
        intent.set_flags(Intent.FLAG_ACTIVITY_NEW_TASK)
        # Uri.parse would ideally return a specific Uri object if your library provides it
        parsed_uri = Uri.parse(uri)
        intent.set_data(parsed_uri)
        device.start_activity(intent)
        return {"success": True, "message": f"Successfully navigated to URI: {uri}"}
    except Exception as e:
        logger.error(f"Navigation failed for URI {uri}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def build_baidu_uri(path: str, params: Dict[str, Any]) -> str:
    """
    Constructs a Baidu Maps URI, filtering out None parameters.
    """
    base_url = BAIDUMAP_NATIVE_BASE_URL
    filtered_params = {k: v for k, v in params.items() if v is not None}
    
    query_string = urlencode(filtered_params) # Correctly encodes parameters
    
    full_uri = f"{base_url}{path}"
    if query_string:
        full_uri += f"?{query_string}"
    return full_uri

# --- Validation Helper Functions ---
def _validate_lat_lng_format(value_str: str, param_name: str) -> Optional[Dict[str, Any]]:
    """
    Validates 'latitude,longitude' format.
    Returns an error dictionary if invalid, None otherwise.
    """
    if not isinstance(value_str, str): 
        return {"success": False, "error": f"Parameter '{param_name}' must be a string, but got type {type(value_str)}."}
    
    parts = value_str.split(',')
    if len(parts) != 2:
        return {
            "success": False,
            "error": f"Parameter '{param_name}' ('{value_str}') has an incorrect format. Expected 'latitude,longitude' (e.g., '40.057406,116.296440')."
        }
    try:
        float(parts[0].strip())
        float(parts[1].strip())
    except ValueError:
        return {
            "success": False,
            "error": f"Parameter '{param_name}' ('{value_str}') contains non-numeric coordinates. Both latitude and longitude must be numbers in 'latitude,longitude' format."
        }
    return None

def _validate_bounds_format(value_str: str, param_name: str) -> Optional[Dict[str, Any]]:
    """
    Validates 'bottomLeftLat,bottomLeftLng,topRightLat,topRightLng' format.
    Returns an error dictionary if invalid, None otherwise.
    """
    if not isinstance(value_str, str):
        return {"success": False, "error": f"Parameter '{param_name}' must be a string, but got type {type(value_str)}."}

    parts = value_str.split(',')
    if len(parts) != 4:
        return {
            "success": False,
            "error": f"Parameter '{param_name}' ('{value_str}') has an incorrect format. Expected 'bottomLeftLat,bottomLeftLng,topRightLat,topRightLng' (e.g., '37.8,-112.5,42.1,118.9')."
        }
    try:
        for part in parts:
            float(part.strip())
    except ValueError:
        return {
            "success": False,
            "error": f"Parameter '{param_name}' ('{value_str}') contains non-numeric values. All four coordinates must be numbers in the 'bottomLeftLat,...,topRightLng' format."
        }
    return None

COMPLEX_LATLNG_EXTRACT_PATTERN = re.compile(r"latlng:(-?\d+\.?\d*,-?\d+\.?\d*)")

def _validate_location_field_format(value_str: str, param_name: str) -> Optional[Dict[str, Any]]:
    """
    Validates complex location fields which can be a name, 'lat,lng', or 'name:...|latlng:lat,lng', etc.
    It specifically checks 'lat,lng' parts if they seem to be intended.
    Returns an error dictionary if an intended coordinate part is invalid, None otherwise.
    """
    if not isinstance(value_str, str):
        return {"success": False, "error": f"Parameter '{param_name}' must be a string, but got type {type(value_str)}."}

    match = COMPLEX_LATLNG_EXTRACT_PATTERN.search(value_str)
    if match:
        coord_part = match.group(1)
        error = _validate_lat_lng_format(coord_part, f"coordinate part identified by 'latlng:' in '{param_name}' ('{value_str}')")
        if error:
            return error
        return None
    elif ',' in value_str and not any(kw in value_str for kw in ["name:", "uid:"]): # Avoid misinterpreting address like "Main Street, City" as simple coords
        # If it has a comma and doesn't look like the complex `latlng:` format,
        # and not other known keywords that might include commas (like 'name:'),
        # it might be intended as simple coordinates.
        return _validate_lat_lng_format(value_str, param_name)
    
    return None

def _validate_coord_type(coord_type: str) -> Optional[Dict[str, Any]]:
    """
    Validates the 'coord_type' parameter.
    Returns an error dictionary if invalid, None otherwise.
    """
    if coord_type not in ["bd09ll", "bd09mc", "gcj02", "wgs84"]:
        return {
            "success": False,
            "error": f"Invalid coordinate type '{coord_type}'. It should be one of 'bd09ll', 'bd09mc', 'gcj02', or 'wgs84'."
        }

def _validate_zoom_level(zoom: Any) -> Optional[Dict[str, Any]]:
    """
    Validates the 'zoom' parameter.
    Returns an error dictionary if invalid, None otherwise.
    """
    if not isinstance(zoom, (int, str)):
        return {
            "success": False,
            "error": f"Invalid zoom level type '{type(zoom)}'. It should be an integer or string."
        }
    if isinstance(zoom, str):
        try:
            zoom = int(zoom)
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid zoom level '{zoom}'. It should be an integer."
            }
    if zoom < 1 or zoom > 22:
        return {
            "success": False,
            "error": f"Invalid zoom level '{zoom}'. It should be between 1 and 22."
        }

def _validate_traffic(traffic: Any) -> Optional[Dict[str, Any]]:
    """
    Validates the 'traffic' parameter.
    Returns an error dictionary if invalid, None otherwise.
    """
    if traffic is None:
        return None
    if not isinstance(traffic, str):
        return {
            "success": False,
            "error": f"Invalid traffic type '{type(traffic)}'. It should be a string."
        }
    if traffic not in ["on", "off"]:
        return {
            "success": False,
            "error": f"Invalid traffic value '{traffic}'. It should be 'on' or 'off'."
        }

# --- End Validation Helper Functions ---

# --- Tool Definitions ---

@mcp.tool(
    description="Shows a Baidu map. Can specify viewport using 'center' and 'zoom', or 'bounds'.",
    annotations={
        "title": "Show Baidu Map",
        "readOnlyHint": True,
        "openWorldHint": True
    }
)
def baidumap_show_map(
    center: Annotated[Optional[str], Field(description='Center point as "latitude,longitude". E.g., "40.057406,116.296440".')] = None,
    bounds: Annotated[Optional[str], Field(description='Map area as "bottomLeftLat,bottomLeftLng,topRightLat,topRightLng". E.g., "37.86,-112.59,42.19,118.94".')] = None,
    zoom: Annotated[Optional[int], Field(description="Map zoom level (e.g., 11).", ge=1, le=22, default=13)] = 13,
    traffic: Annotated[Optional[Literal["on", "off"]], Field(description='Show traffic conditions. Accepts "on" or "off".')] = None,
    coord_type: Annotated[Literal["bd09ll", "bd09mc", "gcj02", "wgs84"], Field(description='Coordinate type (bd09ll, bd09mc, gcj02, wgs84). bd09ll（百度经纬度坐标）bd09mc（百度墨卡托坐标）gcj02（经国测局加密的坐标）wgs84（gps获取的原始坐标）', default="wgs84")] = "wgs84"
) -> dict:
    """
    Displays a Baidu map.
    Either 'center' and 'zoom', or 'bounds' should be specified to define the map's viewport.
    'src' (source identifier) is automatically added.
    """
    function_path = "show"
    if not center and not bounds:
        return {"success": False, "error": "Either 'center' or 'bounds' must be provided for showing the map."}

    if center is not None:
        error = _validate_lat_lng_format(center, "center")
        if error: return error
    
    if bounds is not None:
        error = _validate_bounds_format(bounds, "bounds")
        if error: return error

    error = _validate_zoom_level(zoom)
    if error: return error

    error = _validate_traffic(traffic)
    if error: return error

    error = _validate_coord_type(coord_type)
    if error: return error

    function_path = "show"
    params = {
        "center": center,
        "bounds": bounds,
        "zoom": zoom,
        "traffic": traffic,
        "coord_type": coord_type,
        "src": DEFAULT_SRC, # Use internal default
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated show_map URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Adds a custom marker on the Baidu map at a specified location.",
    annotations={
        "title": "Add Map Marker",
        "readOnlyHint": True, # Or False if you consider adding a marker a change
        "openWorldHint": True
    }
)
def baidumap_add_custom_marker(
    location: Annotated[str, Field(description='Marker position as "latitude,longitude". E.g., "40.057406,116.296440".')],
    title: Annotated[str, Field(description="Title of the marker.")],
    content: Annotated[Optional[str], Field(description="Content/description for the marker.")] = None,
    zoom: Annotated[Optional[int], Field(description="Map zoom level.", ge=1, le=22, default=13)] = 13,
    traffic: Annotated[Optional[Literal["on", "off"]], Field(description='Show traffic conditions.')] = None,
    coord_type: Annotated[Literal["bd09ll", "bd09mc", "gcj02", "wgs84"], Field(description='Coordinate type (bd09ll, bd09mc, gcj02, wgs84). bd09ll（百度经纬度坐标）bd09mc（百度墨卡托坐标）gcj02（经国测局加密的坐标）wgs84（gps获取的原始坐标）', default="wgs84")] = "wgs84"
) -> dict:
    error = _validate_lat_lng_format(location, "location")
    if error: return error
    error = _validate_zoom_level(zoom)
    if error: return error
    error = _validate_traffic(traffic)
    if error: return error
    error = _validate_coord_type(coord_type)
    if error: return error

    function_path = "marker"
    params = {
        "location": location,
        "title": title,
        "content": content,
        "zoom": zoom,
        "traffic": traffic,
        "coord_type": coord_type,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated add_custom_marker URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Performs address geocoding. Displays the map with a marker at the coordinates for the given address.",
    annotations={"title": "Geocode Address", "readOnlyHint": True, "openWorldHint": True}
)
def baidumap_geocode_address(
    address: Annotated[str, Field(description='The address string to geocode. E.g., "北京市海淀区上地信息路9号奎科科技大厦".')]
) -> dict:
    # No specific lat/lng format validation for 'address' field
    if address is None:
        return {"success": False, "error": "Address must be provided for geocoding."}
    if not isinstance(address, str):
        return {"success": False, "error": f"Address must be a string, but got type {type(address)}."}
    if address.strip() == "":
        return {"success": False, "error": "Address cannot be an empty string."}
    function_path = "geocoder"
    params = {
        "address": address,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated geocode_address URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Performs reverse geocoding. Displays location and address information as a marker for the given coordinates.",
    annotations={"title": "Reverse Geocode Location", "readOnlyHint": True, "openWorldHint": True}
)
def baidumap_reverse_geocode_location(
    location: Annotated[str, Field(description='Coordinates as "latitude,longitude". E.g., "39.98871,116.43234".')],
    zoom: Annotated[Optional[int], Field(description="Map zoom level.", ge=1, le=22, default=13)] = 13,
coord_type: Annotated[Literal["bd09ll", "bd09mc", "gcj02", "wgs84"], Field(description='Coordinate type (bd09ll, bd09mc, gcj02, wgs84). bd09ll（百度经纬度坐标）bd09mc（百度墨卡托坐标）gcj02（经国测局加密的坐标）wgs84（gps获取的原始坐标）', default="wgs84")] = "wgs84"
) -> dict:
    error = _validate_lat_lng_format(location, "location")
    if error: return error
    error = _validate_zoom_level(zoom)
    if error: return error
    error = _validate_coord_type(coord_type)
    if error: return error

    function_path = "geocoder"
    params = {
        "location": location,
        "coord_type": coord_type,
        "zoom": zoom,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated reverse_geocode_location URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Searches for Points of Interest (POIs) on Baidu Maps.",
    annotations={"title": "Search POIs", "readOnlyHint": True, "openWorldHint": True}
)
def baidumap_poi_search(
    query: Annotated[str, Field(description='Search keyword. E.g., "美食".')],
    region: Annotated[Optional[str], Field(description='City or county name. E.g., "beijing".')] = None,
    location: Annotated[Optional[str], Field(description='Center point for search as "latitude,longitude" or "latlng:latitude,longitude|name:DisplayName".')] = None,
    bounds: Annotated[Optional[str], Field(description='Search area as "bottomLeftLat,bottomLeftLng,topRightLat,topRightLng".')] = None,
    radius: Annotated[Optional[int], Field(description="Search radius in meters (used with 'location' if 'bounds' is not set).", ge=0)] = None,
coord_type: Annotated[Literal["bd09ll", "bd09mc", "gcj02", "wgs84"], Field(description='Coordinate type (bd09ll, bd09mc, gcj02, wgs84). bd09ll（百度经纬度坐标）bd09mc（百度墨卡托坐标）gcj02（经国测局加密的坐标）wgs84（gps获取的原始坐标）', default="wgs84")] = "wgs84"
) -> dict:
    if query is None:
        return {"success": False, "error": "Query must be provided for POI search."}
    if not isinstance(query, str):
        return {"success": False, "error": f"Query must be a string, but got type {type(query)}."}
    if query.strip() == "":
        return {"success": False, "error": "Query cannot be an empty string."}
    if location is not None:
        error = _validate_location_field_format(location, "location")
        if error: return error

    if bounds is not None:
        error = _validate_bounds_format(bounds, "bounds")
        if error: return error
    if radius is not None and radius < 0:
        return {"success": False, "error": "Radius cannot be negative."}
    error = _validate_coord_type(coord_type)
    if error: return error

    function_path = "place/search"
    params = {
        "query": query,
        "region": region,
        "location": location,
        "bounds": bounds,
        "radius": radius,
        "coord_type": coord_type,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated poi_search URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Plans a route for transit, driving, walking, or riding on Baidu Maps.",
    annotations={"title": "Plan Route", "readOnlyHint": True, "openWorldHint": True}
)
def baidumap_plan_route(
    origin: Annotated[str, Field(description='Starting point. E.g., "天安门", "39.98871,116.43234", or "name:对外经贸大学|latlng:39.98871,116.43234".')],
    destination: Annotated[str, Field(description='Destination point. E.g., "西直门" or "40.055878,116.307854".')],
    mode: Annotated[Literal["transit", "driving", "walking", "riding", "truck", "neweng"], Field(description="Navigation mode. 导航模式， transit（公交）、driving（驾车）、truck（货车）、neweng（新能源，更匹配新能源车的驾车导航，如满足长途出行沿途充电规划等需求）、walking（步行）和riding（骑行）", default="driving")] = "driving",
    coord_type: Annotated[Literal["bd09ll", "bd09mc", "gcj02", "wgs84"], Field(description='Coordinate type (bd09ll, bd09mc, gcj02, wgs84). bd09ll（百度经纬度坐标）bd09mc（百度墨卡托坐标）gcj02（经国测局加密的坐标）wgs84（gps获取的原始坐标）', default="wgs84")] = "wgs84",
    region: Annotated[Optional[str], Field(description="City name for the route.")] = None,
    origin_region: Annotated[Optional[str], Field(description="Origin city.")] = None,
    destination_region: Annotated[Optional[str], Field(description="Destination city.")] = None, 
    origin_uid: Annotated[Optional[str], Field(description="UID of the origin POI.")] = None,
    destination_uid: Annotated[Optional[str], Field(description="UID of the destination POI.")] = None,
    sy: Annotated[Optional[int], Field(description="Transit strategy (0-6). Only for mode=transit. 0：推荐路线 2：少换乘 3：少步行 4：不坐地铁 5：时间短 6：地铁优先")] = None,
    index: Annotated[Optional[int], Field(description="Transit result index (0-based).")] = None,
    target: Annotated[Optional[Literal[0, 1]], Field(description="Transit target (0 for map, 1 for detail).")] = None, 
    car_type: Annotated[Optional[str], Field(description="Driving route preference (e.g., BLK, TIME, DIS, FEE, HIGHWAY, DEFAULT).")] = None,
    via_points_json: Annotated[Optional[str], Field(description="JSON string of via points. E.g., '[{\"name\":\"Point A\",\"lat\":22.1,\"lng\":114.1}]'.")] = None
) -> dict:
    error = _validate_location_field_format(origin, "origin")
    if error: return error
    error = _validate_location_field_format(destination, "destination")
    if error: return error
    if mode not in ["transit", "driving", "walking", "riding", "truck", "neweng"]:
        return {
            "success": False,
            "error": f"Invalid mode '{mode}'. It should be one of 'transit', 'driving', 'walking', 'riding', 'truck', or 'neweng'."
        }
    error = _validate_coord_type(coord_type)
    if error: return error
    if sy is not None and not (0 <= sy <= 6):
        return {
            "success": False,
            "error": f"Invalid sy value '{sy}'. It should be between 0 and 6."
        }
    if index is not None and index < 0:
        return {
            "success": False,
            "error": f"Invalid index value '{index}'. It should be non-negative."
        }
    if target is not None and target not in [0, 1]:
        return {
            "success": False,
            "error": f"Invalid target value '{target}'. It should be 0 or 1. 0 for map, 1 for detail."
        }
    if car_type is not None and car_type not in ["BLK", "TIME", "DIS", "FEE", "HIGHWAY", "DEFAULT"]:
        return {
            "success": False,
            "error": f"Invalid car_type value '{car_type}'. It should be one of 'BLK', 'TIME', 'DIS', 'FEE', 'HIGHWAY', or 'DEFAULT'."
        }
    if via_points_json is not None:
        try:
            # Attempt to parse the JSON string
            import json
            via_points_json = json.loads(via_points_json)
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Invalid via_points_json format. It should be a valid JSON string."
            }
        if not isinstance(via_points_json, list):
            return {
                "success": False,
                "error": f"Invalid via_points_json format. It should be a list of dictionaries."
            }
        for point in via_points_json:
            if not isinstance(point, dict):
                return {
                    "success": False,
                    "error": f"Invalid via_points_json format. Each point should be a dictionary."
                }
            if "name" not in point or "lat" not in point or "lng" not in point:
                return {
                    "success": False,
                    "error": f"Invalid via_points_json format. Each point should contain 'name', 'lat', and 'lng' keys."
                }
            if not isinstance(point["name"], str) or not isinstance(point["lat"], (int, float)) or not isinstance(point["lng"], (int, float)):
                return {
                    "success": False,
                    "error": f"Invalid via_points_json format. 'name' should be a string, and 'lat' and 'lng' should be numbers."
                }
    
    function_path = "direction"
    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "coord_type": coord_type,
        "region": region,
        "origin_region": origin_region,
        "destination_region": destination_region,
        "origin_uid": origin_uid,
        "destination_uid": destination_uid,
        "sy": sy,
        "index": index,
        "target": target,
        "car_type": car_type,
        "viaPoints": via_points_json, 
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated plan_route URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Starts driving navigation to a destination using Baidu Maps.",
    annotations={"title": "Start Driving Navigation", "readOnlyHint": False, "openWorldHint": True, "destructiveHint": False} 
)
def baidumap_start_driving_navigation(
    query: Annotated[str, Field(description='Destination name. E.g., "故宫".')],
    location: Annotated[Optional[str], Field(description='Destination coordinates "latitude,longitude".')] = None,
    uid: Annotated[Optional[str], Field(description="Destination POI UID.")] = None,
    nav_type: Annotated[Optional[Literal["BLK", "TIME", "DIS", "FEE", "HIGHWAY", "DEFAULT"]], Field(description="Navigation preference. BLK:躲避拥堵(自驾); TIME:最短时间(自驾); DIS:最短路程(自驾); FEE:少走高速(自驾); HIGHWAY:高速优先; DEFAULT:推荐（自驾，地图app不选择偏好）;")] = None,
    via_points_json: Annotated[Optional[str], Field(description="JSON string of via points. E.g., '[{\"name\":\"Point A\",\"lat\":22.1,\"lng\":114.1}]'.")] = None,
coord_type: Annotated[Literal["bd09ll", "bd09mc", "gcj02", "wgs84"], Field(description='Coordinate type (bd09ll, bd09mc, gcj02, wgs84). bd09ll（百度经纬度坐标）bd09mc（百度墨卡托坐标）gcj02（经国测局加密的坐标）wgs84（gps获取的原始坐标）', default="wgs84")] = "wgs84"
) -> dict:
    if query is None:
        return {"success": False, "error": "Query must be provided for driving navigation."}
    if not isinstance(query, str):
        return {"success": False, "error": f"Query must be a string, but got type {type(query)}."}
    if query.strip() == "":
        return {"success": False, "error": "Query cannot be an empty string."}
    if location is not None:
        error = _validate_lat_lng_format(location, "location")
        if error: return error
    if uid is not None and not isinstance(uid, str):
        return {"success": False, "error": f"UID must be a string, but got type {type(uid)}."}
    if nav_type is not None and nav_type not in ["BLK", "TIME", "DIS", "FEE", "HIGHWAY", "DEFAULT"]:
        return {
            "success": False,
            "error": f"Invalid nav_type value '{nav_type}'. It should be one of 'BLK', 'TIME', 'DIS', 'FEE', 'HIGHWAY', or 'DEFAULT'. BLK:躲避拥堵(自驾); TIME:最短时间(自驾); DIS:最短路程(自驾); FEE:少走高速(自驾); HIGHWAY:高速优先; DEFAULT:推荐（自驾，地图app不选择偏好）;"
        }
    if via_points_json is not None:
        try:
            # Attempt to parse the JSON string
            import json
            via_points_json = json.loads(via_points_json)
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Invalid via_points_json format. It should be a valid JSON string."
            }
        if not isinstance(via_points_json, list):
            return {
                "success": False,
                "error": f"Invalid via_points_json format. It should be a list of dictionaries."
            }
        for point in via_points_json:
            if not isinstance(point, dict):
                return {
                    "success": False,
                    "error": f"Invalid via_points_json format. Each point should be a dictionary."
                }
            if "name" not in point or "lat" not in point or "lng" not in point:
                return {
                    "success": False,
                    "error": f"Invalid via_points_json format. Each point should contain 'name', 'lat', and 'lng' keys."
                }
    error = _validate_coord_type(coord_type)
    if error: return error
        
    function_path = "navi"
    params = {
        "query": query,
        "location": location,
        "uid": uid,
        "type": nav_type, 
        "viaPoints": via_points_json,
        "coord_type": coord_type,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated start_driving_navigation URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Starts biking navigation from an origin to a destination using Baidu Maps. origin and destination must be in the format of 'latitude,longitude'. before use the tool, you need to obtain the coordinates of the origin and destination points.",
    annotations={"title": "Start Biking Navigation", "readOnlyHint": False, "openWorldHint": True, "destructiveHint": False}
)
def baidumap_start_biking_navigation(
    origin: Annotated[str, Field(description='Origin coordinates "latitude,longitude". E.g., "39.98871,116.43234".')],
    destination: Annotated[str, Field(description='Destination coordinates "latitude,longitude". E.g., "39.91441,116.40405".')],
    coord_type: Annotated[Literal["bd09ll", "bd09mc", "gcj02", "wgs84"], Field(description='Coordinate type (bd09ll, bd09mc, gcj02, wgs84). bd09ll（百度经纬度坐标）bd09mc（百度墨卡托坐标）gcj02（经国测局加密的坐标）wgs84（gps获取的原始坐标）', default="wgs84")] = "wgs84"
) -> dict:
    error = _validate_lat_lng_format(origin, "origin")
    if error: return error
    error = _validate_lat_lng_format(destination, "destination")
    if error: return error
    error = _validate_coord_type(coord_type)
    if error: return error

    function_path = "bikenavi"
    params = {
        "origin": origin,
        "destination": destination,
        "coord_type": coord_type,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated start_biking_navigation URI: {uri}")
    return Navigate(uri)

@mcp.tool( # Added decorator as it seems like an intended tool
    description="Starts walking navigation from an origin to a destination using Baidu Maps. origin and destination must be in the format of 'latitude,longitude'. before use the tool, you need to obtain the coordinates of the origin and destination points.",
    annotations={"title": "Start Walking Navigation", "readOnlyHint": False, "openWorldHint": True, "destructiveHint": False}
)
def baidumap_start_walking_navigation(
    origin: Annotated[str, Field(description='Origin coordinates "latitude,longitude". E.g., "39.98871,116.43234".')],
    destination: Annotated[str, Field(description='Destination coordinates "latitude,longitude". E.g., "39.91441,116.40405".')],
    coord_type: Annotated[Literal["bd09ll", "bd09mc", "gcj02", "wgs84"], Field(description='Coordinate type (bd09ll, bd09mc, gcj02, wgs84). bd09ll（百度经纬度坐标）bd09mc（百度墨卡托坐标）gcj02（经国测局加密的坐标）wgs84（gps获取的原始坐标）', default="wgs84")] = "wgs84"
) -> dict:
    error = _validate_lat_lng_format(origin, "origin")
    if error: return error 
    
    error = _validate_lat_lng_format(destination, "destination")
    if error:
        logging.warning(f"baidumap_start_walking_navigation Error validating destination: {error}") 
        return error
    error = _validate_coord_type(coord_type)
    if error: return error

    function_path = "walknavi"
    params = {
        "origin": origin,
        "destination": destination,
        "coord_type": coord_type,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated start_walking_navigation URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Shows the detail page for a POI on Baidu Maps based on its UID.",
    annotations={"title": "Show POI Detail", "readOnlyHint": True, "openWorldHint": True}
)
def baidumap_show_poi_detail(
    uid: Annotated[str, Field(description='POI ID. E.g., "09185c56d24f7e44f1193763".')],
    show_type: Annotated[Optional[Literal["detail_bar", "detail_page"]], Field(description='Display style: "detail_bar" (map with bottom bar) or "detail_page" (full detail page).', default="detail_bar")] = "detail_bar"
) -> dict:
    # No lat/lng validation for uid
    function_path = "place/detail"
    params = {
        "uid": uid,
        "show_type": show_type,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated show_poi_detail URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description='Opens the "出行早晚报" (Commute Morning/Evening Report) page on Baidu Maps.',
    annotations={"title": "Open Commute Report", "readOnlyHint": True, "openWorldHint": True}
)
def baidumap_open_news_assistant(
    cityid: Annotated[Optional[str], Field(description="City ID to show the report for. If None, shows for the current city.")] = None
) -> dict:
    # No lat/lng validation for cityid
    function_path = "newsassistant"
    params = {
        "cityid": cityid,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated open_news_assistant URI: {uri}")
    return Navigate(uri)

if os.getenv("PC_DEBUG"):
    @mcp.tool(
        description="Geocodes an address using Baidu Maps API. Returns wgs84 coordinates \"latitude,longitude\"",
        annotations={"title": "Geocode Address", "readOnlyHint": True, "openWorldHint": True}
    )
    def baidumap_maps_geocode(
        address: Annotated[str, Field(description='The address string to geocode. E.g., "北京市海淀区上地信息路9号奎科科技大厦".')]
    ) -> str:
        return "40.057406,116.296440"

@mcp.tool(
    description="Gets the current device location (latitude, longitude, address) as a JSON string. Returns an error message on failure.",
    annotations={"title": "Get Current Location", "readOnlyHint": True, "openWorldHint": False} 
)
def get_current_location(
    provider: Annotated[Optional[Literal["network", "gps", "passive", 'fused']], Field(description="Location provider to use.")] = 'network',
) -> str:
    try:
        device = AndroidDevice()
        return device.get_current_location(provider, f"🗺️ Baidu Maps Plugin requesting location\n")
    except Exception as e:
        logger.error(f"Error getting current location: {e}", exc_info=True)
        return f'{{"success": false, "error": "Failed to get current location: {str(e)}"}}'

# Start the server
def run():
    logger.info("Starting Baidu Maps MCP Helper Server...")
    mcp.run(transport="stdio")

def list_tools():
    import anyio
    print(anyio.run(mcp.list_tools))
