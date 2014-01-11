#!/usr/bin/python
# vim: set ts=4 noexpandtab:
# This should work in both recent Python 2 and Python 3.

import socket
import json
import struct
import time
import sys

DEFAULT_THRESHOLD = 10
HIGH_THRESHOLD = 11
HIGHEST_THRESHOLD = 13
LOW_THRESHOLD = 9
LOWEST_THRESHOLD = 8

def sample_bot(host, port):
	s = SocketLayer(host, port)
	gameId = None

	while True:
		# read message
		msg = s.pump()

		if msg["type"] == "error":
			print("The server doesn't know your IP. It saw: " + msg["seen_host"])
			sys.exit(1)

		elif msg["type"] == "request":
			# start new game
			if msg["state"]["game_id"] != gameId:
				gameId = msg["state"]["game_id"]
				print("New game started: " + str(gameId))

			respond_to_request(msg, s)

		elif msg["type"] == "greetings_program":
			print("connected to the server.")

def loop(player, *args):
	while True:
		player(*args)
		#try:
		#	player(*args)
		#except KeyboardInterrupt:
		#	sys.exit(0)
		#except Exception as e:
		#	print(e)
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
	card_to_play = -1
	our_tricks = msg["state"]["your_tricks"]
	their_tricks = msg["state"]["their_tricks"]

	# sort hand
	hand = msg["state"]["hand"]
	hand.sort()

	# responding to played card
	if "card" in msg["state"]:
		value = msg["state"]["card"]
		winning = our_tricks >= their_tricks

		for card in hand:
			if card > value:
				card_to_play = card;
				break;

		if card_to_play == -1:
			# force a tie if we are losing
			if winning == False and value in hand:
				card_to_play = value

			# throw away lowest card
			else:
				card_to_play = hand[0]

		# get rid of lowest card if tie is possible
		if hand[0] == value:
			card_to_play = hand[0]


	# lead with middle card
	else:
		#index = int((len(hand) - 1) / 2);
		#card_to_play = hand[index]
		card_to_play = hand[0]

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
	send_challenge = False

	their_points = state["their_points"]
	our_points = state["your_points"]

	if msg["state"]["your_tricks"] >= 3:
		send_challenge = True

	elif their_points == 9:
		send_challenge = True

	# calculate threshold
	else:
		# calculate average hand value
		hand_value = 0
		avg_hand_value = 0
		num_cards = len(msg["state"]["hand"])

		# calculate hand average value
		hand.reverse()
		count = 0
		for card in msg["state"]["hand"]:
			hand_value += card
			count += 1
			if count == 3:
				break
		hand.reverse()

		avg_hand_value = hand_value / count

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

		if avg_hand_value >= threshold:
			send_challenge = True


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


def respond_to_challenge(msg, s):
	hand_value = 0
	avg_hand_value = 0
	num_cards = len(msg["state"]["hand"])

	# calculate hand average value
	for card in msg["state"]["hand"]:
		hand_value += card

	avg_hand_value = hand_value / num_cards

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
		threshold = HIGH_THRESHOLD

	elif our_tricks == 0 and their_tricks == 2:
		threshold = HIGH_THRESHOLD

	elif our_tricks == 0 and their_tricks == 1:
		threshold = HIGH_THRESHOLD

	if avg_hand_value >= threshold:
		print("accepting challenge: hand = %i; thresh = %i" % ( avg_hand_value, threshold ))
		s.send({
			"type": "move",
			"request_id": msg["request_id"],
			"response": {
				"type": "accept_challenge"
				}
			})
	else:
		print("rejecting challenge: hand = %i; thresh = %i" % ( avg_hand_value, threshold ))
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
