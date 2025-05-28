# server.py
import logging
from typing import Optional, Dict, Any, Literal
from urllib.parse import urlencode # For correct query string encoding

from pydantic import Field
from typing_extensions import Annotated # For older Python versions, ensure typing_extensions is installed if needed. For Python 3.9+ use typing.Annotated

from mcp.server.fastmcp import FastMCP
# Assuming these are your custom classes, ensure they are correctly defined/imported
from xiaozhi_app.plugins import AndroidDevice, Intent, Uri

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

# --- Tool Definitions ---

@mcp.tool(
    description="Shows a Baidu map. Can specify viewport using 'center' and 'zoom', or 'bounds'.",
    annotations={
        "title": "Show Baidu Map",
        "readOnlyHint": True,
        "openWorldHint": True
    }
)
def show_map(
    center: Annotated[Optional[str], Field(description='Center point as "latitude,longitude". E.g., "40.057406,116.296440".')] = None,
    bounds: Annotated[Optional[str], Field(description='Map area as "bottomLeftLat,bottomLeftLng,topRightLat,topRightLng". E.g., "37.86,-112.59,42.19,118.94".')] = None,
    zoom: Annotated[Optional[int], Field(description="Map zoom level (e.g., 11).", ge=1, le=22, default=13)] = 13,
    traffic: Annotated[Optional[Literal["on", "off"]], Field(description='Show traffic conditions. Accepts "on" or "off".')] = None,
    coord_type: Annotated[str, Field(description='Coordinate type (bd09ll, bd09mc, gcj02, wgs84).', default="wgs84")] = "wgs84"
) -> dict:
    """
    Displays a Baidu map.
    Either 'center' and 'zoom', or 'bounds' should be specified to define the map's viewport.
    'src' (source identifier) is automatically added.
    """
    function_path = "show"
    if not center and not bounds:
        # Consider raising ToolError for LLM-friendly errors
        # from fastmcp.exceptions import ToolError
        # raise ToolError("Either 'center' or 'bounds' must be provided for showing the map.")
        return {"success": False, "error": "Either 'center' or 'bounds' must be provided for showing the map."}
    
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
def add_custom_marker(
    location: Annotated[str, Field(description='Marker position as "latitude,longitude". E.g., "40.057406,116.296440".')],
    title: Annotated[str, Field(description="Title of the marker.")],
    content: Annotated[Optional[str], Field(description="Content/description for the marker.")] = None,
    zoom: Annotated[Optional[int], Field(description="Map zoom level.", ge=1, le=22, default=13)] = 13,
    traffic: Annotated[Optional[Literal["on", "off"]], Field(description='Show traffic conditions.')] = None,
    coord_type: Annotated[str, Field(description='Coordinate type.', default="wgs84")] = "wgs84"
) -> dict:
    """
    Adds a custom marker to the map with a title and optional content.
    'src' (source identifier) is automatically added.
    """
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
def geocode_address(
    address: Annotated[str, Field(description='The address string to geocode. E.g., "北京市海淀区上地信息路9号奎科科技大厦".')]
) -> dict:
    """
    Geocodes an address and displays it on the map.
    'src' (source identifier) is automatically added.
    """
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
def reverse_geocode_location(
    location: Annotated[str, Field(description='Coordinates as "latitude,longitude". E.g., "39.98871,116.43234".')],
    zoom: Annotated[Optional[int], Field(description="Map zoom level.", ge=1, le=22, default=13)] = 13,
    coord_type: Annotated[str, Field(description='Coordinate type.', default="wgs84")] = "wgs84"
) -> dict:
    """
    Reverse geocodes coordinates to an address and displays it on the map.
    'src' (source identifier) is automatically added.
    """
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
def poi_search(
    query: Annotated[str, Field(description='Search keyword. E.g., "美食".')],
    region: Annotated[Optional[str], Field(description='City or county name. E.g., "beijing".')] = None,
    location: Annotated[Optional[str], Field(description='Center point for search as "latitude,longitude" or "latlng:latitude,longitude|name:DisplayName".')] = None,
    bounds: Annotated[Optional[str], Field(description='Search area as "bottomLeftLat,bottomLeftLng,topRightLat,topRightLng".')] = None,
    radius: Annotated[Optional[int], Field(description="Search radius in meters (used with 'location' if 'bounds' is not set).", ge=0)] = None,
    coord_type: Annotated[str, Field(description='Coordinate type.', default="wgs84")] = "wgs84"
) -> dict:
    """
    Searches for POIs. Search scope priority: bounds > location+radius > region.
    'src' (source identifier) is automatically added.
    """
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
def plan_route(
    origin: Annotated[str, Field(description='Starting point. E.g., "天安门", "39.98871,116.43234", or "name:对外经贸大学|latlng:39.98871,116.43234".')],
    destination: Annotated[str, Field(description='Destination point. E.g., "西直门" or "40.055878,116.307854".')],
    mode: Annotated[Literal["transit", "driving", "walking", "riding", "truck", "neweng"], Field(description="Navigation mode.", default="driving")] = "driving",
    coord_type: Annotated[str, Field(description='Coordinate type. Baidu API docs state this is mandatory for this specific API call.', default="wgs84")] = "wgs84", # Explicitly noting API requirement
    region: Annotated[Optional[str], Field(description="City name for the route.")] = None,
    origin_region: Annotated[Optional[str], Field(description="Origin city.")] = None,
    destination_region: Annotated[Optional[str], Field(description="Destination city.")] = None, # Added based on common patterns, verify if Baidu API supports this distinct from 'region'
    origin_uid: Annotated[Optional[str], Field(description="UID of the origin POI.")] = None,
    destination_uid: Annotated[Optional[str], Field(description="UID of the destination POI.")] = None,
    sy: Annotated[Optional[int], Field(description="Transit strategy (0-6). Only for mode=transit.")] = None,
    index: Annotated[Optional[int], Field(description="Transit result index (0-based).")] = None,
    target: Annotated[Optional[Literal[0, 1]], Field(description="Transit target (0 for map, 1 for detail).")] = None, # Literal for 0 or 1
    car_type: Annotated[Optional[str], Field(description="Driving route preference (e.g., BLK, TIME, DIS, FEE, HIGHWAY, DEFAULT).")] = None,
    via_points_json: Annotated[Optional[str], Field(description="JSON string of via points. E.g., '[{\"name\":\"Point A\",\"lat\":22.1,\"lng\":114.1}]'.")] = None
) -> dict:
    """
    Plans a route. 'origin' and 'destination' can be names, "lat,lng", or "name:Name|latlng:lat,lng".
    'src' (source identifier) is automatically added. 'coord_type' is marked as required by Baidu's API documentation for this function.
    """
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
        "viaPoints": via_points_json, # API parameter name
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated plan_route URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Starts driving navigation to a destination using Baidu Maps.",
    annotations={"title": "Start Driving Navigation", "readOnlyHint": False, "openWorldHint": True, "destructiveHint": False} # Starting nav is an action
)
def start_driving_navigation(
    query: Annotated[str, Field(description='Destination name. E.g., "故宫".')],
    location: Annotated[Optional[str], Field(description='Destination coordinates "latitude,longitude".')] = None,
    uid: Annotated[Optional[str], Field(description="Destination POI UID.")] = None,
    nav_type: Annotated[Optional[Literal["BLK", "TIME", "DIS", "FEE", "HIGHWAY", "DEFAULT"]], Field(description="Navigation preference.")] = None,
    via_points_json: Annotated[Optional[str], Field(description="JSON string of via points. E.g., '[{\"name\":\"Point A\",\"lat\":22.1,\"lng\":114.1}]'.")] = None,
    coord_type: Annotated[str, Field(description='Coordinate type. Baidu API docs state this is mandatory for this specific API call.', default="wgs84")] = "wgs84" # Explicitly noting API requirement
) -> dict:
    """
    Starts driving navigation.
    'src' (source identifier) is automatically added. 'coord_type' is marked as required by Baidu's API documentation.
    """
    function_path = "navi"
    params = {
        "query": query,
        "location": location,
        "uid": uid,
        "type": nav_type, # API parameter is 'type'
        "viaPoints": via_points_json,
        "coord_type": coord_type,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated start_driving_navigation URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Starts biking navigation from an origin to a destination using Baidu Maps.",
    annotations={"title": "Start Biking Navigation", "readOnlyHint": False, "openWorldHint": True, "destructiveHint": False}
)
def start_biking_navigation(
    origin: Annotated[str, Field(description='Origin coordinates "latitude,longitude". E.g., "39.98871,116.43234".')],
    destination: Annotated[str, Field(description='Destination coordinates "latitude,longitude". E.g., "39.91441,116.40405".')],
    coord_type: Annotated[str, Field(description='Coordinate type. Baidu API docs state this is mandatory for this specific API call.', default="wgs84")] = "wgs84" # Explicitly noting API requirement
) -> dict:
    """
    Starts biking navigation.
    'src' (source identifier) is automatically added. 'coord_type' is marked as required by Baidu's API documentation.
    """
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


def start_walking_navigation(
    origin: Annotated[str, Field(description='Origin coordinates "latitude,longitude". E.g., "39.98871,116.43234".')],
    destination: Annotated[str, Field(description='Destination coordinates "latitude,longitude". E.g., "39.91441,116.40405".')],
    coord_type: Annotated[str, Field(description='Coordinate type. Baidu API docs state this is mandatory for this specific API call.', default="wgs84")] = "wgs84" # Explicitly noting API requirement
) -> dict:
    """
    Starts walking navigation.
   'src' (source identifier) is automatically added. 'coord_type' is marked as required by Baidu's API documentation.
    """
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
def show_poi_detail(
    uid: Annotated[str, Field(description='POI ID. E.g., "09185c56d24f7e44f1193763".')],
    show_type: Annotated[Optional[Literal["detail_bar", "detail_page"]], Field(description='Display style: "detail_bar" (map with bottom bar) or "detail_page" (full detail page).', default="detail_bar")] = "detail_bar"
) -> dict:
    """
    Shows POI details.
    'src' (source identifier) is automatically added.
    """
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
def open_news_assistant(
    cityid: Annotated[Optional[str], Field(description="City ID to show the report for. If None, shows for the current city.")] = None
) -> dict:
    """
    Opens the Commute Morning/Evening Report.
    'src' (source identifier) is automatically added.
    """
    function_path = "newsassistant"
    params = {
        "cityid": cityid,
        "src": DEFAULT_SRC,
    }
    uri = build_baidu_uri(function_path, params)
    logger.info(f"Generated open_news_assistant URI: {uri}")
    return Navigate(uri)

@mcp.tool(
    description="Gets the current device location (latitude, longitude, address) as a JSON string. Returns an error message on failure.",
    annotations={"title": "Get Current Location", "readOnlyHint": True, "openWorldHint": False} # Assuming this is a local device capability
)
def get_current_location(
    provider: Annotated[Optional[Literal["network", "gps", "passive", 'fused']], Field(description="Location provider to use.")] = 'network',
) -> str:
    """
    Retrieves the current geographical location of the device.
    """
    try:
        device = AndroidDevice()
        # The title here is for the Android permission prompt, if applicable
        return device.get_current_location(provider, f"🗺️ Baidu Maps Plugin requesting location\n")
    except Exception as e:
        logger.error(f"Error getting current location: {e}", exc_info=True)
        # Consider returning a JSON error structure or raising ToolError
        # from fastmcp.exceptions import ToolError
        # raise ToolError(f"Failed to get current location: {e}")
        return f'{{"success": false, "error": "Failed to get current location: {str(e)}"}}'

# Start the server
def run():
    logger.info("Starting Baidu Maps MCP Helper Server...")
    # Example test (uncomment to run during development if not using stdio transport directly)
    # result = show_map(center="40.057406,-116.296440", zoom=11)
    # logger.info(f"Test show_map result: {result}")
    # loc_result = get_current_location()
    # logger.info(f"Test get_current_location result: {loc_result}")
    
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run()
