# coding=utf-8
from __future__ import absolute_import

import flask
import logging
import logging.handlers

from octoprint.events import eventManager, Events

import octoprint.plugin

class WhosPrintingPlugin(octoprint.plugin.SettingsPlugin,
                         octoprint.plugin.AssetPlugin,
                         octoprint.plugin.TemplatePlugin,
						 octoprint.plugin.SimpleApiPlugin,
						 octoprint.plugin.EventHandlerPlugin):

	def initialize(self):
		self._logger.setLevel(logging.DEBUG)
		self._logger.info("Who's Printing Plugin [%s] initialized..." % self._identifier)
		self._whos_printing = "";

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			commPorts=["COM1", "COM6"],
			rfidComPort="AUTO",
			raisePrintStartedOnRfidSwipe=True,
			emailcc="", # who to copy email to when sending failed/finished
		)

	def get_settings_restricted_paths(self):
		# only used in OctoPrint versions > 1.2.16
		return dict(admin=[["emailcc"], ["commPorts"], ["rfidComPort"]])

	def get_template_configs(self):
		return [
			#dict(type="navbar", custom_bindings=False),
			dict(type="settings", custom_bindings=False),
			dict(type="tab", name="Whos Printing")
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
	# GET: http://localhost:5000/api/plugin/whosprinting?apikey=<key>
	def on_api_get(self, request):
		#self._logger.info("API Request args: {}".format(request.values.to_dict))

		command = request.values.get("command", ".")
		#self._logger.info("GET Command: {}".format(command))

		if command == "list":
			self._logger.info("Building users list.")
			matched_users = [];

			# returned as a dictionary, can't get at role.
			users = self._user_manager.getAllUsers();
			for user in users:
				self._logger.info("User: {}".format(user))
				# for list, show only the name rather than
				# dump all the users identity info.
				matched_users.append(user["name"]);

			return flask.jsonify(users=matched_users)

		elif command == "get_whos_printing":
			# get the user who is currently printing.
			if self._whos_printing == "":
				self._logger.info("Nobody's printing");
				return

			self._logger.info("Who's printing: {}".format(self._whos_printing))
			user = self._user_manager.findUser(self._whos_printing)
			if user == None:
				self._logger.info("Failed to find user: {0}".format(self._whos_printing));
				return;

			user_settings = user.get_all_settings()
			self._logger.info("User settings: {}".format(user_settings))

			settings = dict(
				username=self._whos_printing,
				displayName=user_settings.get("displayName", self._whos_printing),
				emailAddress=user_settings.get("emailAddress", ""), #Should we be sending this back?
				phoneNumber=user_settings.get("phoneNumber", ""), #Should we be sending this back?
				twitterHandle=user_settings.get("twitterHandle", ""),
				printInPrivate=user_settings.get("printInPrivate", False),
			)
			return flask.jsonify(user=settings)

	# API POST command options
	def get_api_commands(self):
		self._logger.info("On api get commands")

		return dict(
			GeyKeyfobId=[],
			RegisterUser=["username", "password", "displayName", "emailAddress", "phoneNumber", "twitterHandle", "printInPrivate"],
			UpdateUser=["username", "displayName", "emailAddress", "phoneNumber", "twitterHandle", "printInPrivate"],
			PrintStarted=[],
			PrintFinished=[],
			PrintFailed=[],
		)

	# API POST command
	def on_api_command(self, command, data):
		self._logger.info("On api POST Data: {}".format(data))

		if command == "GeyKeyfobId":
			self.do_user_stuff()
		elif command == "RegisterUser":
			# "username", "password", "displayName", "emailAddress", "phoneNumber", "twitterHandle", "printInPrivate", "keyfobId"
			self.register_user(data)
		elif command == "UpdateUser":
			# "username", "displayName", "emailAddress", "phoneNumber", "twitterHandle", "printInPrivate", "keyfobId"
			self.update_user(data)
		elif command == "PrintStarted":
			self._whos_printing = data["whosPrinting"]
			self._logger.info("Set who's printing to: {0}".format(self._whos_printing))
			self.fire_whos_printing()
			self._event_bus.fire(Events.PRINT_STARTED, data)
		elif command == "PrintFinished":
			self._whos_printing = ""
			self._event_bus.fire(Events.PRINT_DONE, data)
			self.fire_whos_printing()
		elif command == "PrintFailed":
			self._whos_printing = ""
			self._event_bus.fire(Events.PRINT_FAILED, data)
			self.fire_whos_printing()

	# Custom event for WhosPrinting
	def fire_whos_printing(self):
		# Find the user. _whos_printing may be empty
		# so we may get a None user if nobody is printing.
		user = self._user_manager.findUser(self._whos_printing)
		if user == None:
			self._event_bus.fire("WhosPrinting", dict(name="", printInPrivate=False))
			return;

		# Get the users setting for print in private so that
		# twitter plugin/live streaming/etc can prevent a
		# picture being made public.
		user_settings = user.get_all_settings()
		print_in_private = user_settings.get("printInPrivate", False),

		self._event_bus.fire("WhosPrinting", dict(username=self._whos_printing, printInPrivate=print_in_private))

	def register_user(self, data):
		# expect the following to be provided in the data.
		# "username", "password", "displayName", "emailAddress", "phoneNumber", "twitterHandle", "printInPrivate", "keyfobId"
		# add the user to the "whosprinting" group so they can be filtered when showing the
		# dropdown option of who's printing.
		# Set API Key to none and not to overwrite.
		self._logger.info("Create user. {0}".format(data.username));
		self._user_manager.addUser(data.username, data.pasword, True, ["user", "whosprinting"],None, False)
		self._logger.info("User created.");

		userSettings = dict(
			displayName = data.displayName,
			emailAddress = data.emailAddress,
			phoneNumber = data.phoneNumber,
			twitter = data.twitterHandle,
			printInPrivate = data.printInPrivate,
			keyfobId = data.keyfobId,
		)
		self._user_manager.changeUserSetting(data.username, userSettings)
		self._logger.info("User settings updated.");

	def update_user(self, data):
		self._logger.info("Update user settings.");
		# "username", "displayName", "emailAddress", "phoneNumber", "twitterHandle", "printInPrivate", "keyfobId"
		userSettings = dict(
			displayName=data.displayName,
			emailAddress=data.emailAddress,
			phoneNumber=data.phoneNumber,
			twitter=data.twitterHandle,
			printInPrivate=data.printInPrivate,
			keyfobId=data.keyfobId,
		)
		self._user_manager.changeUserSetting(data.username, userSettings)
		self._logger.info("User settings updated.");

	# EventHandler Plugin
	def on_event(self, event, payload):
		# Publish the event for the javascript to pick up.
		# TODO: allow settings to disable this
		pluginData = dict(
			eventEvent=event,
			eventPayload=payload)
		self._plugin_manager.send_plugin_message(self._identifier, pluginData)

	# Implementation

	# RFID Card Reader
	# TODO: Raise events ("WhosPrinting.TagSeen", "WhosPrinting.UserSelected"...)


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

