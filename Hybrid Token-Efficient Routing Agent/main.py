from src.router.policy import Policy


def main():
    router = Policy()
    result = router.route("What is the capital of France?")
    print(f"Answer: {result['answer']}")
    print(f"Model:  {result['model_used']}")
    print(f"Conf:   {result['confidence']:.2f}")
    print(f"Tokens: {result['tokens_used']}")


if __name__ == "__main__":
    main()
