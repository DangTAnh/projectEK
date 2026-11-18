def newCardFromType(cardType="", card=""):
  if cardType == "explodingkitten":
    return ExplodingKitten(cardType, card)
  if cardType == "skip":
    return Skip(cardType, card)
  if cardType == "attack2x":
    return Attack2x(cardType, card)
  if cardType == "cat":
    return Cat(cardType, card)
  if cardType == "seethefuture3x":
    return SeeTheFuture3x(cardType, card)
  return Card(cardType, card)
    

class Card:

  def __init__(self, cardType, variant) -> None:
    self.cardType = cardType
    self.variant = variant

  def __str__(self):
    return f"{self.cardType} {self.variant}"

  def activates(self, player, game):
    print("Wow, a blank card. I wonder what will happen next...")
    pass


class ExplodingKitten(Card):

  def __init__(self, cardType, variant) -> None:
    self.defused = False
    super().__init__(cardType, variant)
  def activates(self, player, game):
    if player.hasType("defuse"):  # check if has defuse
      player.playCard(player.getType("defuse"), game.desk)
      print(player.user + " -1 defuse")
      if self.defused is False:  # if never defused befor
        print("There are " + str(game.desk.getSize()) + " position.")
        print()
        index = ""
        while 1:  # ask for bomb place postion
          try:
            index = input("place at ?: ")
            self.defused = True
            player.addBomb(game.desk, self, int(index))
            break
          except Exception as e:
            print("Error:", e)
            continue
        print("added bomb at:", index, end="\n\n")
      else:  # if defused before
        print("This card is defused", end="\n\n")
        player.addGrave(self, game.desk)
    else:  # dead
      print(f"BOOM, {player.user} is dead", end="\n\n")
      game.killPlayer(player)


class Shuffle(Card):
  def __init__(self, cardType, variant) -> None:
    super().__init__(cardType, variant)

  def activates(self, player, game):
    game.desk.shuffleDeck()
    print("Deck shuffled")

# favor
# nope (later on discord)
# seethefuture3x
# cat

class Cat(Card):
  def __init__(self, cardType, variant) -> None:
    super().__init__(cardType, variant)
  def activates(self, player, game):
    ac = player.anotherCat(self)
    if ac:
      print("choose your hihi: ")
      chose = 0
      for player1 in game.players:
        if player1 == player:
          chose += 1
          continue
        print("  ", player1.user)
      chose += int(input(player.user + "  >"))
      player.steal(game.players[chose-1], True)
      player.playCard(ac, game.desk)
    else:
      player.addCard(self)
      game.desk.removeGrave(self)

class Attack2x(Card):
  def __init__(self, cardType, variant) -> None:
    super().__init__(cardType, variant)
  def activates(self, player, game):
    current_player_turn = player.turnToTake
    if current_player_turn == 1:
      current_player_turn = 0
    player.turnToTake = 1
    player.endTurn(game.desk, 0)
    print("Thang tiep theo:",game.nextPlayer.user)
    game.nextPlayer.turnToTake = current_player_turn + 1

class Skip(Card):
  def __init__(self, cardType, variant) -> None:
    super().__init__(cardType, variant)
  def activates(self, player, game):
    player.endTurn(game.desk, 0)

class SeeTheFuture3x(Card):
  def __init__(self, cardType, variant) -> None:
    super().__init__(cardType, variant)
  def activates(self, player, game):
    for card in game.desk.cards[len(game.desk.cards):len(game.desk.cards)-4:-1]:
      print(card)

class Favor(Card):
  def __init__(self, cardType, variant) -> None:
    super().__init__(cardType, variant)
  def activates(self, player, game):
    pass #todo when discord
