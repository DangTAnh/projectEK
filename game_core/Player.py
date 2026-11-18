import random
import game_core.CardManager as CardManager
class Player:

  def __init__(self, user):
    self.user = user
    self.hand = []
    self.isAlive = True
    self.end = False
    self.turnToTake = 0

  def doAction(self, game):
    self.showHand()
    action = input("--------Do stuff: ")
    #debug stuff
    if action == "pg":
      print("Grave: ")
      for c in game.desk.graveCards:
        print("  ", c)
      return PlayerAction()
    if action == "pd":
      print(game.desk.cards)
      return PlayerAction()
    if action == "sh":
      self.showHand()
      return PlayerAction()
    if action.startswith("gc"):
      try:
        ct = action.split(" ")[1]
        cv = action.split(" ")[2]
        card = CardManager.newCardFromType(ct, cv)
        print(type(card))
        self.addCard(card)
      except:
        print("you dum dum forgot arguments")
    if action == "d":
      print("draw")
      return PlayerAction("endturn", self.endTurn(game.desk, 1))
    if action == "pt":
      print("Turns left: ",self.turnToTake)
    if action == "p":
      if not self.hand:
        print("You don't have any cards left.")
        return PlayerAction()
      try:
        while True:
          inp = int(input("Which card do you want to play? (Press 0 to cancel): "))
          if inp == 0:
            return PlayerAction()
          if inp < 1 or inp > len(self.hand):
            print("You just have " + str(len(self.hand)) + " cards.")
          else:
            break
      except ValueError:
        print("Enter a number")
        return PlayerAction()
      selectedCard = self.hand[inp - 1] 
      self.playCard(selectedCard, game.desk)
      return PlayerAction("playcard", selectedCard)
      
    try:
      return PlayerAction("playcard", game.playCard(self.user, self.playCard(self.hand[int(action)], game.desk)))
    except Exception:
      return PlayerAction("Error: playcard, card not found")

  def hasType(self, type):
    for card in self.hand:
      if card.cardType == type:
        return True
    return False

  def anotherCat(self, card):
    for c in self.hand:
      if c.cardType == "cat" and c.variant == card.variant:
        return c
    return None
  
  def getType(self, type):
    for card in self.hand:
      if card.cardType == type:
        return card
    return None

  def addCard(self, card):
    self.hand.append(card)

  def removeCard(self, card):
    self.hand.remove(card)
    return card

  def drawCard(self, desk):
    card = desk.drawCard()
    if card:
      print("drawn", card)
      print()
      self.hand.append(card)
    return card

  def drawNCard(self, desk, n):
    for i in range(n):
      self.drawCard(desk)

  def playCard(self, card, desk):
    if card not in self.hand:
      raise Exception("no fucking card")
    self.addGrave(card, desk)
    return card

  def addGrave(self, card, desk):
    if card not in self.hand:
      raise Exception("no fucking card")
    self.hand.remove(card)
    desk.addGrave(card)

  def endTurn(self, desk, n):
    self.end = True
    self.turnToTake = max(0, self.turnToTake - 1)
    card_lst = []
    for i in range(n):
      card_lst.append(self.drawCard(desk))
    return card_lst

  def showHand(self):
    print(self.user, "hand: ")
    for card in self.hand:
      print("  ", str(card))

  def addBomb(self, desk, card, index):
    if card not in self.hand:
      raise Exception("no fucking card")
    self.hand.remove(card)
    desk.insertCard(index, card)

  def unAlive(self, desk):
    self.isAlive = False
    self.turnToTake = -1
    self.showHand()
    print()
    for i in range(len(self.hand) - 1, -1, -1):
      self.addGrave(self.hand[i], desk)

  def steal(self, player, blind):
    if player.isAlive:
      while 1:
        print("HEHE CARDS: ")
        order = [x for x in range(len(player.hand))]
        random.shuffle(order)
        for j, i in enumerate(order):
          show = "?????"
          if not blind:
            show = player.hand[i]
          print(j+1, "  ", show)
        chose = int(input("i steal this: "))
        if chose <= 0 or chose > len(player.hand):
          print("you dum dum")
          continue
        card = player.removeCard(player.hand[chose-1])
        print(card)
        self.addCard(card)
        return card
  
class PlayerAction: #This is a class to make it easier to send info to Game

  def __init__(self, action = "", *args) -> None:
    self.action = action
    self.args = args
