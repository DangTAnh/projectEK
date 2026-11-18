import random, time
from game_core.Desk import Desk
from game_core.Player import Player, PlayerAction
import multiprocessing
from game_core.CardManager import Card


class Game:
  def __init__(self, players) -> None:
    self.desk = Desk()
    self.players = players
    self.maxPlayer = 0
    self.NoPlayer = len(players)
    self.playerAlive = 0
    self.turn_order = []
    self.current_turn_order =[]
    self.current_player_index = 0
    self.nopeActivated = False
    self.sleeptime = 0
    self.nextPlayer = None

  def newPlayer(self, user):
    player = Player(user)
    self.players.append(player)
    self.NoPlayer += 1
    self.playerAlive += 1

  def removePlayer(self, user):
    for player in self.players:
      if player.user == user:
        self.players.remove(player)
        return True
    return False

  
  def giveDefuse(self):
    for player in self.players:  # add defuse
      card = self.desk.getCardByType("defuse")
      if card is None:
        raise Exception("Not enough defuse cards")

      player.addCard(card)
      print("added defuse for " + player.user)
      self.desk.removeCard(card)
      
  def giveCardFromDesk(self, player, cardType):
    card = self.desk.getCardByType(cardType)
    if card is None:
      print("Not enough " + cardType + " cards")
      return
    player.addCard(card)
    self.desk.removeCard(card)
    print("added " + cardType + " for " + player.user)
  
  def deal(self):
    onHandCard = 4
    for player in self.players: # iterate through every player
      for c in range(onHandCard): # draw 4 cards
        card = self.desk.drawCard()
        
        if card.cardType == "explodingkitten": # if is bomb
          if player.hasType("defuse"): # if has defuse
            print("Da go bom", end="\n\n")
            self.desk.graveCards.append(card) # bomb => grave
            player.addGrave(player.getType("defuse"), self.desk) # defuse => grave
            continue
          else: # else dead
            print(f"BOOM, {player.user} is dead")
            if player.isAlive:
              self.killPlayer(player)
        
        player.addCard(card)

  def killPlayer(self, player):
    player.unAlive(self.desk)
    self.playerAlive -= 1

  
  def start(self):
  
    self.desk.loadDesk("original") # load desk
    print("loaded desk")
    
    self.desk.shuffleDeck() # shuffle
    print("shuffled")
    
    self.maxPlayer = self.desk.getSizeByType("defuse")  #setmaxplayer == defuse
    self.giveDefuse()
    self.deal()
    print("Da chia bai xong", end="\n\n")  #deal
  
  def gameloop(self):
    print("start")
    self.turn_order = [x for x in range(self.NoPlayer)] 
    print(self.NoPlayer)
    print(self.turn_order)# turn order
    random.shuffle(self.turn_order) # shuffle turn order
    while 1:
      self.current_turn_order = self.turn_order
      for j, i in enumerate(self.current_turn_order):
        current_player = self.players[i]
        current_player.turnToTake += 1
        self.current_player_index = j
        try:
          self.nextPlayer = self.players[self.current_turn_order[(self.current_player_index + 1)%len(self.players)]]
        except:
          print(self.current_player_index)
          
        if not current_player.isAlive: # check if is alive
          continue # next player
        
        while current_player.turnToTake > 0:
          print("yumm")
          while 1:
            if self.playerAlive <= 1:  # check if game ended
              print(current_player.user, "wins")
              return
            print("turn: " + str(current_player.user))
            action = current_player.doAction(self)  # get player action
  
            if action.action == "playcard": # if action is playcard
              card = action.args[0]
              print(current_player.user + " played " + str(card), end='\n\n')
              self.handlePlayCard(current_player, card)
              #wait for nope card
              #todo: wait for nope
  
            if action.action == "endturn": # if action is endturn
              drawncards = action.args[0]
              self.handleDrawnCard(current_player, drawncards)
  
            if current_player.end:
              current_player.end = False
              break
          
  def handlePlayCard(self, player, card):
    exceptionList = ["nope", "defuse", "explodingkitten"]
    
    if card.cardType in exceptionList:
      return
    card.activates(player, self)

  def handleDrawnCard(self, player, cards):
    for card in cards:
      if card.cardType == "explodingkitten":  #check if is bomb
        card.activates(player, self)
    
  def end(self):
    pass
