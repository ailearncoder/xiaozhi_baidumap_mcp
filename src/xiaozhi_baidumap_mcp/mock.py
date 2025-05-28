# --- Mocking xiaozhi_app.plugins for standalone runnable example ---
class AndroidDevice:
    def get_current_location(self, provider: str, title: str) -> str:
        # Mock implementation
        logger.info(f"Mock: Getting current location for {provider} with title: {title}")
        return '{"latitude": 39.9, "longitude": 116.3, "address": "Mock Location"}'

    def start_activity(self, intent):
        # Mock implementation
        logger.info(f"Mock: Starting activity with intent: data={intent.get_data()}, action={intent.get_action()}, flags={intent.get_flags()}")
        pass

class Intent:
    ACTION_VIEW = "android.intent.action.VIEW"
    FLAG_ACTIVITY_NEW_TASK = 0x10000000 # Example flag value

    def __init__(self, action: str):
        self._action = action
        self._data = None
        self._flags = 0

    def set_flags(self, flags: int):
        self._flags = flags

    def get_flags(self) -> int:
        return self._flags

    def set_data(self, uri):
        self._data = uri

    def get_data(self):
        return self._data
    
    def get_action(self):
        return self._action

class Uri:
    @staticmethod
    def parse(uri_string: str):
        # Mock implementation
        return uri_string # In a real scenario, this would parse and return a Uri object
# --- End Mock ---