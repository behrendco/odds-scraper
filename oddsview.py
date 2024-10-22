import asyncio
import websockets
import json
import requests
from typing import Optional, List, Dict
from traceback import print_exc

CHANNEL_TITLES = {
    "MONEYLINE": ["best_ml", "moneyline"],
    "SPREAD": ["best_ms", "spread"]
}

async def stream(
    uri: str,
    subscription_payload: str
) -> None:
    """
    Sets up a connection with the server which is pushing new odds to the OddsView website.
    Awaits further updates. As soon as updated odds information arrives it prints all the relevant
    information regarding the specific odds update.

    The function is meant to be called from the live_odds_stream method inside the OddsView class

    :param uri str: URI for the web server
    :param subscription_payload str: Subscription message to send to the server with info regarding 
                                     the odds data we want to receive updates on

    :rtype: None, returns nothing, continues collecting and presenting new odds info until stopped
    """
    try:
        ws = await websockets.connect(uri)
        await ws.send(subscription_payload)

        while True:
            try:
                message = await ws.recv()
                message_json = json.loads(message)
                channel = message_json["channel"]
                payload = message_json["payload"]
                
                print(channel)
                print(payload)
                print()
            except websockets.WebSocketException:
                print_exc()
                break
            except Exception as e:
                print(f"Error: {e}")
                print_exc()

        await ws.close()
    except Exception as e:
        print(f"Error: {e}")
        print_exc()

class OddsView:
    def __init__(self) -> None:
        """
        Initializes a class object

        :rtype: None
        """
        self.live_games_uri = "https://49pzwry2rc.execute-api.us-east-1.amazonaws.com/prod/getLiveGames"
        self.historical_odds_uri = "https://49pzwry2rc.execute-api.us-east-1.amazonaws.com/prod/getHistoricalOdds"
        self.ws_uri = "wss://ws.openodds.gg/ws"

    def get_live_games(
        self, 
        sport: Optional[str] = None, 
        live: Optional[str] = None
    ) -> List[Dict]:
        """
        Finds all games and corresponding ids, dates, names, teams/players, sports, leagues, and markets

        :param sport str: If a sport is specified [else it's None], results will be filtered by that sport
                          Ex: basketball
        :param live str: If live is specified [else it's None], results will be filtered by that category.
                         Ex: true/false

        :rtype: List[Dict]
        """
        params = {}
        if sport:
            params["sport"] = sport
        if live:
            params["live"] = live

        response = requests.get(self.live_games_uri, params=params).json()
        return response["body"]["live_games"]

    def get_historical_odds(
        self,
        outcome_id: Optional[str] = None,
        live: Optional[str] = None,
        from_: Optional[str] = None
    ) -> None:
        pass

    def get_game_channels(
        self,
        live_games: List[Dict]
    ) -> List[Dict]:
        """
        Collects relevant channels to subscribe to for each live game

        :param live_games List[Dict]: List of current live games fetched from the get_live_games method

        :rtype: List[Dict]
        """
        games_to_stream = []
        for live_game in live_games:
            game = {}
            game["game_id"] = live_game["game_id"]
            game["channels"] = []
            for market_id, market in live_game["markets"].items():
                if market["market_type"] in CHANNEL_TITLES.keys():
                    for outcome_id, outcome in market["outcomes"].items():
                        for channel_title in CHANNEL_TITLES[market["market_type"]]:
                            game["channels"].append(f"{channel_title}.{outcome_id}")
            games_to_stream.append(game)

        return games_to_stream

    async def live_odds_stream(self) -> None:
        """
        Sets up the live odds stream by calling the async stream function

        :rtype: None
        """
        live_games = self.get_live_games()
        print(json.dumps(live_games, indent=2))
        print()

        games = self.get_game_channels(live_games)
        tasks = [asyncio.create_task(
            stream(
                uri=self.ws_uri, 
                subscription_payload=json.dumps({"filtered_sportsbooks": ["PINNY"], "action": "filter"})
            )
        )]
        for game in games:
            game_id = game["game_id"]
            tasks.append(asyncio.create_task(
                stream(
                    uri=self.ws_uri, 
                    subscription_payload=json.dumps({"channel": f"game_state.{game_id}", "action": "subscribe"})
                )
            ))
            for channel in game["channels"]:
                tasks.append(asyncio.create_task(
                    stream(
                        uri=self.ws_uri, 
                        subscription_payload=json.dumps({"channel": channel, "action": "subscribe"})
                    )
                ))

        [await task for task in tasks]

async def main():
    ov = OddsView()
    await ov.live_odds_stream()

if __name__ == "__main__":
    asyncio.run(main())