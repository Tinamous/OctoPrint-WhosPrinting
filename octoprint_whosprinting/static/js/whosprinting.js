/*
 * View model for OctoPrint-WhosPrinting
 *
 * Author: Tinamous
 * License: AGPLv3
 */
$(function() {

    function WhosPrintingViewModel(parameters) {
        var self = this;

        self.pluginId = "whosprinting";

        self.loginStateViewModel = parameters[0];
        self.settingsViewModel = parameters[1];
        self.printer = parameters[2];

        // Status message for who's printing as used in the navbar
        self.statusMessage = ko.observable("Who's Printing?");

        // Becomes true if somebody has
        self.isInUse = ko.observable(false);
        self.printerUser = ko.observable("Who's Printing?");

        // If the current user is not logged. in
        self.notLoggedIn = ko.computed(function() {
            return !self.loginStateViewModel.isUser();
        })

        // If we have someone flagged as printing
        self.isPrinting = ko.observable(false);
        self.isNotPrinting = ko.computed(function() {
            return !self.isPrinting();
        })

        // The user who is currently printing.
        self.whosPrinting = ko.observable();
        self.whosPrintingHistory = ko.observableArray([]);
        // The possible users who can be selected for Who's Printing
        self.whosPrintingList = ko.observableArray([]);
        // The user who's been selected in the select/options list.
        self.selectedWhosPrinting = ko.observable("");
        self.unknownTagSeen = ko.observable(false);

        self.canIndicatePrinting = ko.computed(function() {
            if (self.selectedWhosPrinting() === undefined) {
                return false;
            }
            return true;
        }, this);


        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings.plugins.whosprinting;
			console.log("Who's Printing Settings: " + self.settings );
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "whosprinting") {
                return;
            }

            // A known tag will set the WhosPrinting event
            if (data.eventEvent == "WhosPrinting") {
                console.log("Who's Printing Event from onDataUpdater");
                // If a known tag is see then the WhosPrinting event is fired
                self.unknownTagSeen(false);
                self.getWhosPrinting();
            }

            // If the tag was seen and it is unknown.
            if (data.eventEvent == "UnknownRfidTagSeen") {
                console.log("Unknown tag seen. TagId:" + data.eventPayload.tagId);
                // If in normal mode, show a "Unknown Tag, please register" message
                // If not logged in it won't be visible anyway
                self.unknownTagSeen(true);
                // This needs to be cleared if the tag was used for registering.
            }

            // A known tag will set the WhosPrinting event
        };

        self.onUserLoggedIn = function(user) {
            self.populateUsers();
            self.getWhosPrinting();
        };

        // Get the list of users that can be shown in the populate users list.
        self.populateUsers = function() {
            console.log("Getting users for who's printing selection.");

            OctoPrint
                .simpleApiGet(self.pluginId + "?command=list", {})
                .done(self.getUsersResponseHandler);
        };

        // GET request to get the list of users to show in the who's printing dropdown.
        self.getUsersResponseHandler = function(response) {
            console.log("Populate users response: " + response);
            self.whosPrintingList(response.users);
        };

        // Get who is currentyl printing.
        self.getWhosPrinting = function() {
            console.log("Getting users for who's printing selection.");

            OctoPrint
                .simpleApiGet(self.pluginId + "?command=get_whos_printing", {})
                .done(self.getWhosPrintingResponseHandler );
        };

        self.getWhosPrintingResponseHandler = function(response){
            if (response && response.user) {
                console.log("Somebodys printing: " + response.user);
                self.whosPrinting(response.user);
                self.isPrinting(true);
            } else {
                // Nobody is printing.
                if (self.whosPrinting() != null) {
                    self.whosPrintingHistory.push(self.whosPrinting())
                }
                self.isPrinting(false);
                self.whosPrinting(null);
            }
        };

        // UI Indication that the person in the select list has started printing.
        self.startedPrinting = function() {
            self.isPrinting(true);

            console.log("User: " + self.selectedWhosPrinting());

            var payload = {
                username: self.selectedWhosPrinting()
            };
            OctoPrint.simpleApiCommand(self.pluginId, "PrintStarted", payload, {});
        };

        self.printFailed = function() {
            self.isPrinting(false);
            var payload = { };
            OctoPrint.simpleApiCommand(self.pluginId, "PrintFailed", payload, {});
        };

        self.printFinished = function() {
            self.isPrinting(false);
            var payload = { };
            OctoPrint.simpleApiCommand(self.pluginId, "PrintFinished", payload, {});
        };

        self.testKeyFob = function() {

            var payload = { };
            OctoPrint.simpleApiCommand(self.pluginId, "FakeTag", payload, {});
        };
    }

    // view model class, parameters for constructor, container to bind to
    // New style config .
    OCTOPRINT_VIEWMODELS.push({
        construct: WhosPrintingViewModel,
        additionalNames: [],
        dependencies: [ "loginStateViewModel", "settingsViewModel", "printerStateViewModel" ],
        optional: [],
        elements: ["#navbar_plugin_whosprinting", "#tab_plugin_whosprinting"]
    });
});
