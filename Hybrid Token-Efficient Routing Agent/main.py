from src.router.policy import Policy

def main():
    
    router = Policy()
    result = router.route("What is the capital of France?") # Example Prompt
    print(result)

if __name__ == "__main__":
    main()