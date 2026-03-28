import argparse
import openapi_client
from openapi_client.rest import ApiException
from pprint import pprint
from uuid import UUID

configuration = openapi_client.Configuration(
    host = "http://172.28.40.187:40000"
)

def main() -> None:
    parser = argparse.ArgumentParser(description="Mühle solver")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode.",
    )
    args = parser.parse_args()

    if args.test:
        print("Hello, World! (test mode)")
    else:
        print("Hello, World!")

    with openapi_client.ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = openapi_client.DefaultApi(api_client)
        game = api_instance.create_game()
        print(game)
        player = api_instance.add_player(game.id, "player1")
        print(player)

if __name__ == "__main__":
    main()