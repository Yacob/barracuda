#!/usr/bin/python
# vim: set ts=4 noexpandtab:
# This should work in both recent Python 2 and Python 3.

import socket
import json
import struct
import time
import sys

DEFAULT_THRESHOLD = 12
HIGH_THRESHOLD = 12
HIGHEST_THRESHOLD = 13
LOW_THRESHOLD = 9.5
LOWEST_THRESHOLD = 9

DUMB_MODE = False

MAGIC_SCALE = 10

cards_played = {}
hands_played = 0
hand_id = -1

def shuffle_deck ():
	global hands_played
	global cards_played

	print("deck state")
	for value in cards_played:
		print("%s: %i" % (value, cards_played[value]))

	print("shuffling deck after %i" % hands_played)
	for value in range(1, 14):
		cards_played["%i" % value] = 8

def update_deck (msg):
	global cards_played

	our_number = msg["your_player_num"]

	if "by" not in msg["result"]:
		return

	if "card" not in msg["result"]:
		return

	player = msg["result"]["by"]
	value = msg["result"]["card"]

	# don't double count
	if our_number == player:
		return

	cards_played["%i" % value] -= 1

	#print("there are now %i '%i' cards" % (cards_played["%i" % value], value))


def sample_bot(host, port):
	global hands_played
	global hand_id
	global hands_played

	s = SocketLayer(host, port)
	gameId = None

	while True:
		# read message
		msg = s.pump()

		if msg["type"] == "result":
			update_deck(msg)

		if msg["type"] == "error":
			print("The server doesn't know your IP. It saw: " + msg["seen_host"])
			sys.exit(1)

		elif msg["type"] == "request":
			# start new game
			if msg["state"]["game_id"] != gameId:
				gameId = msg["state"]["game_id"]
				hands_played = 0
				shuffle_deck()
				print("New game started: " + str(gameId))

			# get new hand attributes
			if msg["state"]["hand_id"] != hand_id:
				hand_id = msg["state"]["hand_id"]
				hands_played += 1
				print("hands played: %i" % hands_played)

				# update deck with our cards
				for value in msg["state"]["hand"]:
					cards_played["%i" % value] -= 1
					print ("there are now %i '%i' cards" % (cards_played["%i" % value], value))

			# run main response
			respond_to_request(msg, s)

			# shuffle deck
			if hands_played >= 10:
				shuffle_deck()
				hands_played = 0

		elif msg["type"] == "greetings_program":
			print("connected to the server.")

def loop(player, *args):
	while True:
		#player(*args)
		try:
			player(*args)
		except KeyboardInterrupt:
			sys.exit(0)
		except Exception as e:
			print(e)
		time.sleep(10)


def respond_to_request(msg, s):
	sent_challenge = False

	# automatically challenge if already won
	if msg["state"]["can_challenge"] == True:
		sent_challenge = send_challenge(msg, s)

	if sent_challenge == True:
		return

	elif msg["request"] == "request_card":
		play_card(msg, s)

	elif msg["request"] == "challenge_offered":
		respond_to_challenge(msg, s)


def play_card(msg, s):
	global cards_played
	state = msg["state"]
	card_to_play = -1
	our_tricks = msg["state"]["your_tricks"]
	their_tricks = msg["state"]["their_tricks"]
	tricks_to_tie = (5 - state["total_tricks"] + our_tricks + their_tricks) / 2

	# sort hand
	hand = msg["state"]["hand"]
	hand.sort()

	# responding to played card
	if "card" in msg["state"]:
		value = msg["state"]["card"]

		cards_played["%i" % value] -= 1
		print ("there are now %i '%i' cards" % (cards_played["%i" % value], value))

		for card in hand:
			if tricks_to_tie - their_tricks <= 1 and card >= value:
				card_to_play = card;
				break
			elif card > value:
				card_to_play = card;
				break;

		# force a tie if we are losing
		#if value in hand and our_tricks <= their_tricks:
		#	card_to_play = value

		if card_to_play == -1:
			card_to_play = hand[0]

		# get rid of lowest card if tie is possible
		if hand[0] == value:
			card_to_play = hand[0]


	else:
		#index = int((len(hand) - 1) / 2);
		#card_to_play = hand[index]

		# calculates the number of relevant cards
		num_top_cards = tricks_to_tie - our_tricks;
		hand.reverse()

		# the card immediately after our top cards is at index num_top_cards
		try:
			card_to_play = hand[int(num_top_cards + 0.5)]

		# in the case where it is out of bounds, select the lowest top card
		except:
			card_to_play = hand[-1]

		hand.reverse()


	s.send({
		"type": "move",
		"request_id": msg["request_id"],
		"response": {
			"type": "play_card",
			"card": card_to_play
			}
		})


def send_challenge (msg, s):
	state = msg["state"]
	hand = state["hand"]
	send_challenge = False

	their_points = state["their_points"]
	their_tricks = state["their_tricks"]

	our_points = state["your_points"]
	our_tricks = state["your_tricks"]

	# calculate tricks needed to win
	tricks_to_tie = (5 - state["total_tricks"] + our_tricks + their_tricks) / 2

	# always challenge if we'll atleast tie
	if msg["state"]["your_tricks"] >= tricks_to_tie:
		send_challenge = True

	# last ditch challenge
	elif their_points == 9:
		send_challenge = True

	# why would we challeng if we are in the lead?
	elif our_points == 9:
		return

	# don't challenge if we can't win
	elif state["their_tricks"] >= tricks_to_tie:
		return

	elif "card" in state:
		our_card = -1
		their_card = state["card"]

		# calculate card to play
		hand.sort()
		hand.reverse()
		for card in hand:
			if card > their_card:
				our_card = card
				break

		# if our card is better and we can tie
		if our_card > their_card and our_tricks >= tricks_to_tie - 1:
			send_challenge = True

		# if we tie
		elif our_card == their_card and our_tricks >= tricks_to_tie:
			send_challenge = True

		elif len(hand) == 1 and our_tricks == their_tricks and their_card <= 10:
			send_challenge = True

		else:
			send_challenge = meet_threshold(msg, tricks_to_tie)



	# calculate threshold
	else:
		send_challenge = meet_threshold(msg, tricks_to_tie)


	if send_challenge == True:
		print("issuing challenge")
		s.send({
			"type": "move",
			"request_id": msg["request_id"],
			"response": {
				"type": "offer_challenge"
			}
		})

	return send_challenge

def meet_threshold (msg, tricks_to_tie):
	state = msg["state"]
	num_tricks = state["total_tricks"]
	our_tricks = state["your_tricks"]
	their_tricks = state["their_tricks"]

	hand_value = 0
	avg_hand_value = 0
	hand = state["hand"]

	# calculate hand average value
	hand.sort()
	hand.reverse()
	count = 0
	for card in msg["state"]["hand"]:
		hand_value += card
		count += 1
		if count >= tricks_to_tie - our_tricks:
			break

	avg_hand_value = hand_value / count

	# calculate threshold
	threshold = DEFAULT_THRESHOLD

	our_tricks = msg["state"]["your_tricks"]
	their_tricks = msg["state"]["their_tricks"]

	if our_tricks == 2 and their_tricks == 0:
		threshold = LOWEST_THRESHOLD

	elif our_tricks == 2 and their_tricks == 1:
		threshold = LOW_THRESHOLD

	elif our_tricks == 2 and their_tricks == 2:
		threshold = HIGHEST_THRESHOLD

	elif our_tricks == 1 and their_tricks == 2:
		threshold = HIGHEST_THRESHOLD

	elif our_tricks == 0 and their_tricks == 2:
		threshold = HIGHEST_THRESHOLD

	elif our_tricks == 0 and their_tricks == 1:
		threshold = HIGH_THRESHOLD

	# only happens if we played a card
	if "card" in state and msg["request"] == "challenge_offered":
		threshold += 1

	if state["your_points"] == 9:
		threshold -= 1.5

	if DUMB_MODE == True:
		threshold = 7

	threshold_scalar = 0
	total_cards_in_deck = 0
	for key in cards_played:
		threshold_scalar += (cards_played[key] * int(key))
		total_cards_in_deck += cards_played[key]

	threshold_scalar /= (total_cards_in_deck * 7 + MAGIC_SCALE)

	print("scalar is %.2f" % threshold_scalar)
	threshold *= threshold_scalar

	if (avg_hand_value > threshold or avg_hand_value >= HIGHEST_THRESHOLD):
		print("accepting challenge: hand = %i; thresh = %i" % ( avg_hand_value, threshold ))
	else:
		print("rejecting challenge: hand = %i; thresh = %i" % ( avg_hand_value, threshold ))

	return avg_hand_value > threshold or avg_hand_value >= HIGHEST_THRESHOLD



def respond_to_challenge(msg, s):
	state = msg["state"]
	send_challenge = False

	their_points = state["their_points"]
	their_tricks = state["their_tricks"]

	our_points = state["your_points"]
	our_tricks = state["your_tricks"]

	# calculate tricks needed to win
	tricks_to_tie = (5 - state["total_tricks"] + our_tricks + their_tricks) / 2

	accept = False
	if meet_threshold(msg, tricks_to_tie):
		accept = True

	elif their_points == 9:
		accept = True

	if their_tricks >= tricks_to_tie:
		accept = False

	if accept == True:
		s.send({
			"type": "move",
			"request_id": msg["request_id"],
			"response": {
				"type": "accept_challenge"
				}
			})
	else:
		s.send({
			"type": "move",
			"request_id": msg["request_id"],
			"response": {
				"type": "reject_challenge"
			}
		})



class SocketLayer:
	def __init__(self, host, port):
		self.s = socket.socket()
		self.s.connect((host, port))

	def pump(self):
		"""Gets the next message from the socket."""
		sizebytes = self.s.recv(4)
		(size,) = struct.unpack("!L", sizebytes)

		msg = []
		bytesToGet = size
		while bytesToGet > 0:
			b = self.s.recv(bytesToGet)
			bytesToGet -= len(b)
			msg.append(b)

		msg = "".join([chunk.decode('utf-8') for chunk in msg])

		return json.loads(msg)

	def send(self, obj):
		"""Send a JSON message down the socket."""
		b = json.dumps(obj)
		length = struct.pack("!L", len(b))
		self.s.send(length + b.encode('utf-8'))

	def raw_send(self, data):
		self.s.send(data)

if __name__ == "__main__":
	loop(sample_bot, "cuda.contest", 9999)
