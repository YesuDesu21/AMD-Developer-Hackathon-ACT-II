class Validators:

    @staticmethod
    def extract_confidence(response) -> float:
        import json
        # If it's already a dictionary, skip json.loads
        if isinstance(response, dict):
            return response.get("confidence", 0.0)
            
        try:
            data = json.loads(response)
            return data.get("confidence", 0.0)
        except (json.JSONDecodeError, TypeError):
            return 0.0

    @staticmethod
    def validate_format(response: str, task_type: str = None) -> bool:
        if not response or len(response.strip()) == 0:
            return False
        return True
