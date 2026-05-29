class OpenClawAdapter:
    """Adapter interface to hand tasks into OpenClaw (future integration).

    Implementations should implement `submit_task(task_json)` and handle
    authentication and callbacks.
    """
    def __init__(self, endpoint: str = None, api_key: str = None):
        self.endpoint = endpoint
        self.api_key = api_key

    def submit_task(self, task_json: dict) -> dict:
        # placeholder: send task_json to OpenClaw via its API
        raise NotImplementedError('OpenClaw integration not implemented')
