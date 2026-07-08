from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient
from src.router.validators import Validators
from src.utils.logger import Logger


class Policy:

    def __init__(self):
        self.local_client = LocalClient()
        self.remote_client = RemoteClient()
        self.logger = Logger()
        self.validators = Validators()
        self.threshold = 0.8

    def route(self, task):
        local_result = self.local_client.run_local(task)

        local_answer = local_result.get("answer", "")
        confidence = self.validators.extract_confidence(local_result)  # ← pass whole dict
        format_ok = self.validators.validate_format(local_answer)   # ← pass answer string

        print(f"Local response: {local_answer}")
        print(f"Confidence: {confidence}")
        print(f"Format ok: {format_ok}")

        if confidence >= self.threshold and format_ok:
            self.logger.log("local", task)
            return local_answer
    
        remote_result = self.remote_client.generate(task)
        remote_answer = remote_result.get("answer", "") if isinstance(remote_result, dict) else str(remote_result)
        self.logger.log("remote", task)
        return remote_answer
