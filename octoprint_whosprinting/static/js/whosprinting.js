/*
 * View model for OctoPrint-WhosPrinting
 *
 * Author: Tinamous
 * License: AGPLv3
 */
$(function() {

    function RegisterWhosPrintingUserViewModel() {
        var self = this;
        self.username = ko.observable("");
        self.password = ko.observable("");
        self.confirmPassword = ko.observable("");
        self.keyfobId = ko.observable("");
        self.displayName = ko.observable("");
        self.emailAddress = ko.observable("");
        self.phoneNumber = ko.observable("");
        self.twitterHandle = ko.observable("");
        self.printInPrivate = ko.observable(false);
        self.pluginId = "whosprinting";

        self.register = function() {
            console.log("Register user. Plugin Id: " + self.pluginId)
            var registerUser = {
                username: self.username(),
                password: self.password(),
                keyfobId: self.keyfobId(),
                displayName: self.displayName(),
                emailAddress: self.emailAddress(),
                phoneNumber: self.phoneNumber(),
                twitterHandle: self.twitterHandle(),
                printInPrivate: self.printInPrivate()
            };
            OctoPrint.simpleApiCommand(self.pluginId, "RegisterUser", registerUser, {});
        }

        return self;
    }

    function WhosPrintingUser() {
        var self = this;
        self.displayName = ko.observable("");
        self.emailAddress = ko.observable("");
        self.phoneNumber = ko.observable("");
        self.twitterHandle = ko.observable("");
        self.printInPrivate = ko.observable(false);
        return self;
    }

    function WhosPrintingViewModel(parameters) {
        var self = this;

        console.log("Who's Printing?");
        self.pluginId = "whosprinting";

        self.loginStateViewModel = parameters[0];
        self.settingsViewModel = parameters[1];
        self.printer = parameters[2];

        // Registration view model.
        self.registerUserViewModel = new RegisterWhosPrintingUserViewModel();

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

            if (data.eventEvent == "WhosPrinting") {
                console.log("Who's Printing Event from onDataUpdater");
                self.getWhosPrinting();
            }
        };

        self.onUserLoggedIn = function(user) {
            console.warn("CurrentUser: " + user);
            //self.currentUser(user);

            console.log("*** on User Logged In")
            self.populateUsers();
            self.getWhosPrinting();
        };

        // Custom event "WhosPrinting"
        self.onEventWhosPrinting = function(payload) {
            console.log("WhosPrinting event seen...");

            // Update the who's printing.
            self.getWhosPrinting();
        };

        // onEvent<EventName>(payload)

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
                console.log("Nobody's printing. :-(")
            }
        };

        // UI Indication that the person in the select list has started printing.
        self.startedPrinting = function() {
            self.isPrinting(true);

            console.log("User: " + self.selectedWhosPrinting());

            var payload = {
                name: "FakePrint",
                path:".",
                origin:"local",
                file: "/gcode/FakePrint.gcode",
                whosPrinting: self.selectedWhosPrinting()};
            OctoPrint.simpleApiCommand(self.pluginId, "PrintStarted", payload, {});
        };

        self.printFailed = function() {
            self.isPrinting(false);
            //$('#whosprinting_confirm_print_failed').modal('hide');

            var payload = {
                name: "FakePrint",
                path:".",
                origin:"local",
                file: "/gcode/FakePrint.gcode",
                whosPrinting: ""};
            OctoPrint.simpleApiCommand(self.pluginId, "PrintFailed", payload, {});
        };

        self.printFinished = function() {
            self.isPrinting(false);
            //$('#whosprinting_confirm_print_finished').modal('hide');

            var payload = {
                name: "FakePrint",
                path:".",
                origin:"local",
                file: "/gcode/FakePrint.gcode",
                whosPrinting: ""};
            OctoPrint.simpleApiCommand(self.pluginId, "PrintFinished", payload, {});
        };

        self.showRegister = function() {
            console.log("Resister clicked. Plugin: ");
            $('#whosprinting_register_dialog').modal('show');
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
