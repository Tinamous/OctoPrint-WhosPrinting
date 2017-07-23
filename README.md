# OctoPrint-WhosPrinting

Please Note: This is designed for use with OctoPrint where OctoPrint isn't used to print (e.g. display/webcam only), this plugin currently raises events inside OctoPrint that may confuse OctoPrint if you are actually printing.

This plugin is useful where OctoPrint is used in a multi-user environment, it allows the person printing to select themself from a list of users and indicate that they are printing.

The user details are then shown on OctoPrint sessions (where a user is logged in), so that the person printing can be contacted should they need to be.

Print Finished and Print Failed buttons are made available to indicate if the print has finished or failed (and this may be used to notify the user).

Note: Initial version is intended for use where OctoPrint isn't itself controlling the printer, hence we don't have the logged in user starting a print, or printing events from the printer.

By firing PrintStarted, PrintFinished or PrintFailed events this also lets other plugins (e.g. timelapse/twitter/email) function without a connected printer.

A register method is provided so that users can self register for the who's printing plugin

A new system wide event is added "WhosPrinting" with a payload of {name, printInPrivate}. Where printInPrivate is true other plugins can prevent photographs from being made public (e.g. a Twitter plugin).

When the user selects themselves from the drop down box and presses [Printing], if the "Fire PrintStarted Event" setting is set then a PrintStarted event will be fired.

Users register for the Who's Printing and this registers them on the OctoPrint login system so they can login another time. Additional properties are added to the user settings dictionary of:

* displayName
* emailAddress
* phoneNumber
* twitterHandle
* printInPrivate

Note that if the OctoPrint instance is internet connected it may be possible for the users details (phone number, email, etc) to be gained by 3rd parties by registering and viewing the who's printing instance.

When using this without a connected printer (i.e. its currently intended operation), enable the virtual printer and set it to automatically connect.

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/Tinamous/OctoPrint-WhosPrinting/archive/master.zip

## Configuration

The Who's Printing supports the following configuration options:

### RFID Swipe Enabled

Enable this setting if you wish to have Who's Printing assign a user by RFID tag

### RFID Reader Type

Select the type of reader connected. Current support is only for the Micro RWD Hitag2 reader from IB Technology, or None.

### RFID Comm Port

The comm port for the RFID reader to use. (Auto is available but won't work).

### Fire Printer Events

For standalone operation (i.e. without a connected printer) setting a user as "Who's Printing" and marking the print as finished/failed can be used to fire the printer events which can then be used to trigger plugins.

e.g. It is possible to use the timelapse mode by firing the printing event and printDone event's via Who's Printing using this option which will cause the video stream to be captured and made into a a timelapse.

If you are printing from OctoPrint you should disable this option to prevent confusing OctoPrint and the plugins.

### Show Email

If your OctoPrint is isolated from the internet you can use this option to display the Who's Printing user email address on the screen when a (different) user is logged in (e.g. Default login for OctoPrint on a display at the printer).

### Show Phone Number

As Show Email, if selected will make the Who's Printing user phone number visible on the UI.

### Open Registration

When checked this allowes for any user to register on the OctoPrint instance so they may be listed in the Who's Printed selection.

Note that their is currently no way for users to change email/phone number/twitter handle/rfid tag once registered. It will need to be done by the OctoPrint administrator (i.e. you) by editing the users.yaml file.
