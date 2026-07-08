from src.router.policy import Policy


def main():
    router = Policy()
    result = router.route("What is the capital of France?")
    print(result)


if __name__ == "__main__":
    main()
