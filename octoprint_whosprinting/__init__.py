# coding=utf-8
from __future__ import absolute_import

import flask
import logging
import logging.handlers

from octoprint.events import eventManager, Events
from octoprint.util import RepeatedTimer

import octoprint.plugin

from .microRWDHiTag2Reader import microRWDHiTag2Reader
from .nullTagReader import nullTagReader


class WhosPrintingPlugin(octoprint.plugin.StartupPlugin,
						 octoprint.plugin.ShutdownPlugin,
                         octoprint.plugin.SettingsPlugin,
                         octoprint.plugin.AssetPlugin,
                         octoprint.plugin.TemplatePlugin,
                         octoprint.plugin.SimpleApiPlugin,
                         octoprint.plugin.EventHandlerPlugin,
                         octoprint.plugin.BlueprintPlugin):

	def initialize(self):
		self._logger.setLevel(logging.DEBUG)
		self._logger.info("Who's Printing Plugin [%s] initialized..." % self._identifier)
		# The username of the person that is printing.
		self._whos_printing = ""
		self._check_tags_timer = None
		self._last_tag = None
		self._rfidReader = nullTagReader(self._logger)

	# Startup complete we can not get to the settings.
	def on_after_startup(self):
		self._logger.info("Who's Printing Plugin on_after_startup")
		self.initialize_rfid_tag_reader()

	def on_shutdown(self):
		self._check_tags_timer = None
		self._rfidReader.close()


	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			useRfidReader=True,
			rfidComPort="AUTO",
			firePrinterEvents=True,
			showEmailAddress=False,
			showPhoneNumber=False,
			canRegister=True,
			rfidReaderType="Micro RWD HiTag2",
			readerOptions=["None", "Micro RWD HiTag2"],
			tinamous_url="",
		)

	def on_settings_save(self, data):
		self._logger.info("on_settings_save")
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		# Handle posisble port or RFID reader changed
		self.initialize_rfid_tag_reader()

	def get_template_configs(self):
		return [
			# dict(type="navbar", custom_bindings=False),
			dict(type="settings", custom_bindings=False),
			dict(type="tab", name="Who's Printing")
		]

	##~~ AssetPlugin mixin

	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/whosprinting.js"],
			css=["css/whosprinting.css"],
			less=["less/whosprinting.less"]
		)

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
		return dict(
			whosprinting=dict(
				displayName="Who's Printing Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="Tinamous",
				repo="OctoPrint-WhosPrinting",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/Tinamous/OctoPrint-WhosPrinting/archive/{target_version}.zip"
			)
		)

	# API GET command
	# GET: http://localhost:5000/api/plugin/whosprinting?command=<command>&apikey=<key>
	# commands:
	#   list: Lists the users who can be assigned as printing.
	#   get_whos_printing: Returns the current user details for the user that is printing.
	def on_api_get(self, request):
		# self._logger.info("API Request args: {}".format(request.values.to_dict))

		command = request.values.get("command", ".")
		# self._logger.info("GET Command: {}".format(command))

		if command == "list":
			self._logger.info("Building users list.")
			matched_users = []

			# returned as a dictionary, can't get at role.
			users = self._user_manager.getAllUsers()
			for user in users:
				# for list, show only the name rather than
				# dump all the users identity info.
				matched_users.append(user["name"])

			return flask.jsonify(users=matched_users)

		elif command == "get_whos_printing":
			# get the user who is currently printing.
			if self._whos_printing == "":
				self._logger.info("Nobody's printing")
				return

			self._logger.info("Who's printing: {}".format(self._whos_printing))
			user = self._user_manager.findUser(self._whos_printing)
			if user == None:
				self._logger.info("Failed to find user: {0}".format(self._whos_printing))
				return

			settings = self.get_whos_printing_details(user)

			return flask.jsonify(user=settings)

	# API POST command options
	def get_api_commands(self):
		self._logger.info("On api get commands")

		return dict(
			GeyKeyfobId=[],
			RegisterUser=["username", "password", "displayName", "emailAddress", "phoneNumber", "twitterUsername",
						  "printInPrivate"],
			UpdateUser=["username", "displayName", "emailAddress", "phoneNumber", "twitterUsername", "printInPrivate"],
			PrintStarted=["username"],
			PrintFinished=[],
			PrintFailed=[],
			FakeTag=[],
		)

	# API POST command
	def on_api_command(self, command, data):
		self._logger.info("On api POST Data: {}".format(data))

		if command == "RegisterUser":
			# data contains: "username", "password", "displayName", "emailAddress", "phoneNumber", "twitterUsername", "tinamousHandle", "slackHandle", "printInPrivate", "keyfobId"
			self.register_user(data)
		elif command == "UpdateUser":
			# data contains: "username", "displayName", "emailAddress", "phoneNumber", "twitterUsername", "tinamousHandle", "slackHandle", "printInPrivate", "keyfobId"
			self.update_user(data)
		elif command == "PrintStarted":
			# data contains: username
			self.set_whos_printing_print_started(data)
		elif command == "PrintFinished":
			# data expected to be empty
			self.set_whos_printing_print_finished(data)
		elif command == "PrintFailed":
			# data expected to be empty
			self.set_whos_printing_print_failed(data)
		elif command == "FakeTag":
			payload = dict(keyfobId="123789852")
			pluginData = dict(eventEvent="UnknownRfidTagSeen", eventPayload=payload)
			self._plugin_manager.send_plugin_message(self._identifier, pluginData)

	# Blueprint for registration needs to be unprotected.
	def is_blueprint_protected(self):
		self._logger.info("blueprint protected...")
		return False

	# API BluePrint implementation for registration
	# Needs to be done as blueprint so that protection can be disabled.
	@octoprint.plugin.BlueprintPlugin.route("/register", methods=["POST"])
	def api_register_user(self):
		self._logger.info("Blueprint register user called")

		if not "username" in flask.request.values:
			return flask.make_response("Username is required.", 400)

		if not "password" in flask.request.values:
			return flask.make_response("Username is required.", 400)

		canRegister = self._settings.get(['canRegister'])
		if not canRegister:
			return flask.make_response("Open Registration is disabled.", 400)

		payload = dict(
			username = flask.request.values["username"],
			password = flask.request.values["password"],
			displayName = flask.request.values["displayName"],
			emailAddress = flask.request.values["emailAddress"],
			phoneNumber = flask.request.values["phoneNumber"],
			twitterUsername = flask.request.values["twitterUsername"],
			printInPrivate = flask.request.values["printInPrivate"],
			keyfobId = flask.request.values["keyfobId"],
		)

		if self.register_user(payload):
			return flask.make_response("Created.", 201)
		else :
			return flask.make_response("Failed to register user.", 501)

	# EventHandler Plugin
	def on_event(self, event, payload):
		# Custom event raised by Who's Printing RFIX Dat
		if event == "RfidTagSeen":
			self.handle_rfid_tag_seen_event(payload)

	##########################################
	# Implementation
	##########################################

	def handle_rfid_tag_seen_event(self, payload):
		tagId = payload["tagId"]
		self._logger.info("RFID Tag Seen: " + tagId)

		# Raise the plugin message for an RfidTagSeen.
		pluginData = dict(eventEvent="RfidTagSeen", eventPayload=payload)
		self._plugin_manager.send_plugin_message(self._identifier, pluginData)

		# Find the user this tag belongs to
		user = self.find_user_from_tag(tagId)

		if (user == None):
			self._logger.info("Did not find a user for the tag.")
			pluginData = dict(eventEvent="UnknownRfidTagSeen", eventPayload=payload)
			self._plugin_manager.send_plugin_message(self._identifier, pluginData)
			return

		useRfidReader = self._settings.get(['useRfidReader'])
		if not self._settings.get(["useRfidReader"]):
			self._logger.info("Not setting Who's Printing as RFDI Swipe is disabled in settings.")
			return

		# User was found so handle a known user swipping the RFID
		data = dict(username=user["name"])
		self.set_whos_printing_print_started(data)
		self._logger.info("raising print started from Rfid tag Swipe")

	# Indicate that a user is printing as set from the Who's Printing Tab
	# data contains: name, path, origin,file, username
	def set_whos_printing_print_started(self, data):

		# TODO: If somebody is currently printing and a new tag seen...
		# Either the last persons print was finished and they didn't
		# get flagged as finished and a new printer has come along
		# Or somebody tagged whena print was under way (e.g to register).
		# Assume it's a new printer...

		if self._whos_printing:
			self._logger.error("Somebody is already printing, we need to mark that as finished first")



		# Store the user that is currently printing.
		self._whos_printing = data["username"]
		self._logger.info("Set who's printing to: {0}".format(self._whos_printing))
		self.fire_whos_printing()
		self.fire_printer_event(Events.PRINT_STARTED, data)

	# Indicate that a users print has finished (successfully) as set from the Who's Printing Tab
	# data contains: name, path, origin,file
	def set_whos_printing_print_finished(self, data):
		self.fire_printer_event(Events.PRINT_DONE, data)
		self._whos_printing = ""
		self.fire_whos_printing()

	# Indicate that a users print has failed :-( as set from the Who's Printing Tab
	# data contains: name, path, origin,file
	def set_whos_printing_print_failed(self, data):
		self.fire_printer_event(Events.PRINT_FAILED, data)
		self._whos_printing = ""
		self.fire_whos_printing()

	# Fire a OctoPrint Printing event (if settings allow this).
	# e.g. PrintDone, PrintStarted, PrintFailed.
	# On a real install with an actual printer this probably isn't desirable
	# On a monitoring install it lets other plugins do their thing.
	# Injected into data is 'username' property with the username
	# of the user that is printing. This then allows other
	# plugins (e.g. email/twitter) to pick this up for notifications.
	# It is not an official part of the OctoPrint event.
	def fire_printer_event(self, event, data):
		if self._settings.get(['firePrinterEvents']):
			self._logger.info("Firing printer event '{0}' for who's printing update".format(event))

			# Inject the username of the user that is/was printing.
			data["username"] = self._whos_printing
			# Setup other properties expected for the printer event
			# name is the filename, overload it here with the who's printing
			# to allow timelapse naming based on the user name.
			data["name"] = self._whos_printing
			data["path"] = "."
			data["origin"] = "local"
			data["time"] = 60  # HACK: used in PrintDone
			# Deprecated since 1.3.0
			data["file"] = "/gcode/" + self._whos_printing + ".gcode"
			self._event_bus.fire(event, data)
		else:
			self._logger.info("Not firing printer event '{0}' as it's disabled by config".format(event))

	# Fire the Custom OctoPrint wide event "WhosPrinting"
	def fire_whos_printing(self):
		eventName = "WhosPrinting"

		# Find the user. _whos_printing may be empty
		# so we may get a None user if nobody is printing.
		user = self._user_manager.findUser(self._whos_printing)
		if user == None:
			self._event_bus.fire(eventName, dict(username=""))
		else:
			self._event_bus.fire(eventName, dict(username=self._whos_printing))

		# Send the plugin message as well to update UI's
		payload = dict(username=self._whos_printing)
		pluginData = dict(eventEvent=eventName, eventPayload=payload)
		self._plugin_manager.send_plugin_message(self._identifier, pluginData)

	##########################################
	# User registration / Management / Setings
	##########################################

	def register_user(self, data):
		# expect the following to be provided in the data.
		# "username", "password", "displayName", "emailAddress", "phoneNumber", "twitterUsername", "printInPrivate", "keyfobId"
		# add the user to the "whosprinting" group so they can be filtered when showing the
		# dropdown option of who's printing.
		# Set API Key to none and not to overwrite.

		if not self._settings.get(['canRegister']):
			self._logger.error("Attempting to register when it is disabled")
			return False

		username = data["username"]
		self._logger.info("Create user. {0}".format(username))
		self._user_manager.addUser(username, data["password"], True, ["user", "whosprinting"], None, False)
		self._logger.info("User created.")

		userSettings = dict(
			displayName=data["displayName"],
			emailAddress=data["emailAddress"],
			phoneNumber=data["phoneNumber"],
			twitter=data["twitterUsername"],
			tinamous=data["tinamousUsername"],
			slack=data["slackUsername"],
			printInPrivate=data.get("printInPrivate", False),
			keyfobId=data["keyfobId"],
		)
		self._user_manager.changeUserSettings(username, userSettings)
		self._logger.info("User settings updated.")

		return True

	# Do we need to raise an event to indicate that a user has been added
	# so that the who's printing selector can be updated.
	# or is SETTINGS_UPDATED fired?

	def update_user(self, data):
		self._logger.info("Update user settings.")
		# "username", "displayName", "emailAddress", "phoneNumber", "twitterUsername", "printInPrivate", "keyfobId"
		userSettings = dict(
			displayName=data["displayName"],
			emailAddress=data["emailAddress"],
			phoneNumber=data["phoneNumber"],
			twitter=data["twitterUsername"],
			tinamous=data["tinamousUsername"],
			slack=data["slackUsername"],
			printInPrivate=data.get("printInPrivate", False),
			keyfobId=data["keyfobId"],
		)
		self._user_manager.changeUserSettings(data["username"], userSettings)
		self._logger.info("User settings updated.")

	def get_whos_printing_details(self, user):
		user_settings = user.get_all_settings()
		self._logger.info("User settings from UserManager: {}".format(user_settings))

		email_address = None
		if self._settings.get(['showEmailAddress']):
			email_address = user_settings.get("emailAddress")

		phone_number = None
		if self._settings.get(['showPhoneNumber']):
			phone_number = user_settings.get("phoneNumber")

		displayName = user_settings.get("displayName");
		if displayName == None:
			displayName = self._whos_printing

		settings = dict(
			username=self._whos_printing,
			displayName=displayName,
			emailAddress=email_address,
			phoneNumber=phone_number,
			twitterUsername=user_settings.get("twitter"),
			tinamousUsername=user_settings.get("tinamous"),
			slackUsername=user_settings.get("slack"),
			printInPrivate=user_settings.get("printInPrivate"),
		)

		return settings

	def find_user_from_tag(self, tagId):
		self._logger.info("Getting user for tag {0}".format(tagId))

		users = self._user_manager.getAllUsers()
		for user in users:
			user_settings = user["settings"]
			user_key_fob = user_settings.get("keyfobId")
			#user_key_fob = user.get_setting("keyfobId")
			if tagId == user_key_fob:
				return user

		self._logger.info("No user found for tag")
		return None

	# RFID Card Reader handling
	def initialize_rfid_tag_reader(self):
		self._logger.info("Initializing RFID Tag Reader")
		# Close the old reader (nullReader if not reader selected).
		if self._check_tags_timer:
			self._check_tags_timer = None

		if self._rfidReader:
			self._rfidReader.close()

		readerType = self._settings.get(['rfidReaderType'])
		if readerType == "Micro RWD HiTag2":
			self._logger.info("Initializing Micro RWD HiTag2")
			self._rfidReader = microRWDHiTag2Reader(self._logger)
		else:
			self._logger.info("Using null tag reader")
			self._rfidReader = nullTagReader(self._logger)

		try:
			rfidPort = self._settings.get(['rfidComPort'])
			if rfidPort:
				self._logger.info("Opening port: {0} for RFID reader.".format(rfidPort))
				self._rfidReader.open(rfidPort)
			else:
				self._logger.error("No COM port set for RFID reader")

			readerVersion = self._rfidReader.read_version()
			if readerVersion:
				self._logger.info("Reader version: {0}".format(readerVersion))
				# set the timer to check the reader for a tag
				self.startTimer()
		except IOError as e:
			self._logger.error("Failed to open the serial port.")


	def startTimer(self):
		self._logger.info("Starting timer to read RFID tag")
		self._check_tags_timer = RepeatedTimer(0.5, self.check_tag, None, None, True)
		self._check_tags_timer.start()

	def check_tag(self):
		try:
			tag = self._rfidReader.seekTag()

			# If it's the same tag as before, user has not released the tag
			# so just ignore it.
			if tag == self._last_tag:
				return

			if tag:
				self._logger.info("Got a tag!!!! TagId: {0}".format(tag))
				# Raise the tag seen event.
				payload = dict(tagId=tag)
				self._event_bus.fire("RfidTagSeen", payload)
				self._last_tag = tag
			else:
				# Clear last tag ready for a new one...
				self._last_tag = None
				self._logger.info("Tag removed")
		except IOError as e:
			self._logger.exception("Error reading tag. Exception: {0}".format(e))
			#TODO: Disable after too many errors
		except Exception as e:
			self._logger.exception("Unhandled error reading tag. Exception: {0}".format(e))



# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Who's Printing Plugin"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = WhosPrintingPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
