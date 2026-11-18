import random
import game_core.CardManager as CardManager
import json


class Desk:

  def __init__(self) -> None:
    self.cards = []
    self.graveCards = []

  def getSize(self):
    return len(self.cards)

  def getSizeByType(self, type):
    n = 0
    for card in self.cards:
      if card.cardType == type:
        n += 1
    return n
  
  #Gets
  def getCardByType(self, type):
    for card in self.cards:
      if card.cardType == type:
        return card
    return None
  def getCard(self, index):  #Get at index
    return self.cards[index]

  def getCardTop(self):  #Get at top
    return self.getCard(-1)

  def getCardBot(self):  #Get at bot
    return self.getCard(0)

  #Adds
  def addCardTop(self, card):  #Add at top
    self.cards.append(card)

  def addCardBot(self, card):  #Add at bottom
    self.cards.insert(0, card)

  def insertCard(self, index, card):  #Add at index
    if index not in range(0, len(self.cards) + 1):
      raise Exception("out of range dumb shit", index)
    self.cards.insert(index, card)

  #Removes
  def removeCard(self, card):  #Remove by card
    self.cards.remove(card)

  def removeCardTop(self):  #Remove top card
    return self.cards.pop(-1)

  def removeCardBot(self):  #Remove bottom card
    return self.cards.pop(0)

  def removeAtIndex(self, index):  #Remove at index
    return self.cards.pop(index)

  def isEmpty(self):
    return self.getSize() == 0

  def drawCard(self):
    if self.isEmpty():
      self.shuffleGrave()
      self.cards.extend(self.graveCards)
      print(self.cards)
      self.graveCards.clear()
      print("WOWW EMPTY!")
    print(self.getSize())
    return self.removeCardTop()

  def loadDesk(self, name):
    with open(f"./resources/desk/{name}.json", "r", encoding="utf-8") as f:
      data = json.loads(f.read())
    cards = data["cards"]
    for cardType in cards:
      for card in cards[cardType]:
        for i in range(cards[cardType][card]):
          self.addCardTop(CardManager.newCardFromType(cardType, card))

  def shuffleDeck(self):
    random.shuffle(self.cards)

  def addGrave(self, card):
    self.graveCards.append(card)

  def getGrave(self, index):
    return self.graveCards[index]

  def removeGrave(self,index: int):
    self.graveCards.pop(index)

  def removeGrave(self, card: CardManager.Card):
    self.graveCards.remove(card)
  
  def shuffleGrave(self):
    self.cards = self.graveCards
    self.graveCards = []
    self.shuffleDeck()
