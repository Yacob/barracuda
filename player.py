#!/usr/bin/python

# This should work in both recent Python 2 and Python 3.

import socket
import json
import struct
import time
import sys

def sample_bot(host, port):
	s = SocketLayer(host, port)

	gameId = None

	while True:
		msg = s.pump()
		if msg["type"] == "error":
			print("The server doesn't know your IP. It saw: " + msg["seen_host"])
			sys.exit(1)

		elif msg["type"] == "request":
			respond_to_request(msg);
		elif msg["type"] == "greetings_program":
			print("Connected to the server.")

def loop(player, *args):
	while True:
		try:
			player(*args)
		except KeyboardInterrupt:
			sys.exit(0)
		except Exception as e:
			print(repr(e))
		time.sleep(10)

def play_card(msg):
	card_to_play = -1
	# sort hand
	hand = msg["state"]["hand"]
	hand.sort()

	# responding to played card
	if "card" in msg["state"]:
		respond_to_card(msg, hand);
		
	# leading with a card
	else:
		card_to_play = hand[0]

	s.send({
		"type": "move",
		"request_id": msg["request_id"],
		"response": {
			"type": "play_card",
			"card": card_to_play
			}
		})

def respond_to_card(msg, hand):
	value = msg["state"]["card"]

	for card in hand:
		if card > value:
			card_to_play = card;
			break;

	if card_to_play == -1:
		card_to_play = hand[0]

def respond_to_request(msg):
	if msg["state"]["game_id"] != gameId:
		gameId = msg["state"]["game_id"]
		print("New game started: " + str(gameId))

	if msg["request"] == "request_card":
		play_card(msg);

	elif msg["request"] == "challenge_offered":
		respond_to_challenge(msg);

def respond_to_challenge(msg):
	hand_value = 0;
	for card in msg["state"]["hand"]:
		hand_value += card
	if (hand_value / (5 - msg["state"]["total_tricks"])) > 11:
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
