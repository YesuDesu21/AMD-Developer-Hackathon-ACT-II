class RemoteClient:
    def generate(self, task: str) -> dict:
        return {
            "answer": f"Remote response to: {task}",
            "confidence": 1.0,
            "is_valid_format": True,
            "error": None,
        }
