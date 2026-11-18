from game_core.Game import Game
from game_core.Player import Player
from game_core.Desk import Desk
from game_core.CardManager import Card
from threading import Thread
for i in range(1):
  game = Game([])

  game.newPlayer("user1")
  game.newPlayer("user2")
  game.newPlayer("user3")
  game.newPlayer("user4")
  game.newPlayer("user5")
  game.newPlayer("user6")

  game.start()

  thread = Thread(target=game.gameloop)
  thread.start()
