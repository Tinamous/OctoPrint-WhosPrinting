# OctoPrint-WhosPrinting

Please Note: This is currently designed for use with OctoPrint where OctoPrint isn't used to print (e.g. display/webcam only). This plugin currently raises events inside OctoPrint that may confuse OctoPrint if you are actually printing.

This plugin is useful where OctoPrint is used in a multi-user environment, it allows the person printing to select themself from a list of users and indicate that they are printing.

The user details are then shown on OctoPrint sessions (where a user is logged in), so that the person printing can be contacted should they need to be.

Print Finished and Print Failed buttons are made available to indicate if the print has finished or failed (and this may be used to notify the user).

Note: Initial version is intended for use where OctoPrint isn't itself controlling the printer, hence we don't have the logged in user starting a print, or printing events from the printer.

By firing PrintStarted, PrintFinished or PrintFailed events this also lets other plugins (e.g. timelapse/twitter/email) function without a connected printer.

A register method is provided so that users can self register for the who's printing plugin

A new system wide event is added "WhosPrinting" with a payload of {name, printInPrivate}. Where printInPrivate is true other plugins can prevent photographs from being made public (e.g. a Twitter plugin).

When the user selects themself from the drop down box and presses [Printing], if the "Fire PrintStarted Event" setting is set then a PrintStarted event will be fired.

Users register for the Who's Printing and this registers them on the OctoPrint login system so they can login another time. Additional properties are added to the user settings dictionary of:

* displayName
* emailAddress
* phoneNumber
* twitterHandle
* printInPrivate

Note that if the OctoPrint instance is internet connectable it may be possible for the uesrs details to be gained by 3rd parites (by registering and viewing the who's printing instance.

When using this without a connected printer (i.e. its currently intended operaiton), enable the virtual printer and set it to automatically connect.

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/Tinamous/OctoPrint-WhosPrinting/archive/master.zip

**TODO:** Describe how to install your plugin, if more needs to be done than just installing it via pip or through
the plugin manager.

## Configuration

**TODO:** Describe your plugin's configuration options (if any).
