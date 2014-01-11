#!/usr/bin/python
# vim: set ts=4 noexpandtab:
# This should work in both recent Python 2 and Python 3.

import socket
import json
import struct
import time
import sys

C_THRESHOLD = 10

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
	# automatically challenge if already won
	if msg["state"]["can_challenge"] and msg["state"]["your_tricks"] >= 3:
		s.send({
			"type": "offer_challenge",
			"request_id": msg["request_id"]
		})

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
			else
				card_to_play = hand[0]


	# lead with middle card
	else:
		index = int((len(hand) - 1) / 2);
		card_to_play = hand[index]

	s.send({
		"type": "move",
		"request_id": msg["request_id"],
		"response": {
			"type": "play_card",
			"card": card_to_play
			}
		})


def respond_to_challenge(msg, s):
	if msg["state"]["your_tricks"] >= msg["state"]["their_tricks"]:
		hand_value = 0
		for card in msg["state"]["hand"]:
			hand_value += card
		if (hand_value / (5 - msg["state"]["total_tricks"])) >= C_THRESHOLD:
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
