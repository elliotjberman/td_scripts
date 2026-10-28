loadAPI(18);
host.setShouldFailOnDeprecatedUse(true);
host.defineController("Live Visuals", "Audio Engine Handoff", "1.0",
    "db64b6fe-2427-41d7-9010-7e333cc58c65", "Elliot");
host.defineMidiPorts(0, 0);

// Read-only metadata beside the official TDBitwig controller.
// One coherent packet per host flush; no timers, MIDI routing, or DAW writes.
var application, connection;
var dirty = true;

function requestState() {
    dirty = true;
    host.requestFlush();
}

function init() {
    application = host.createApplication();
    application.projectName().addValueObserver(requestState);
    application.hasActiveEngine().addValueObserver(requestState);
    var osc = host.getOscModule();
    connection = osc.connectToUdpServer("127.0.0.1", 9100, null);
    var requests = osc.createAddressSpace();
    requests.registerMethod("/live/engine/get", "*", "Read current project engine state", requestState);
    osc.createUdpServer(9101, requests);
}

function flush() {
    if (!dirty || !connection) return;
    dirty = false;
    connection.sendMessage("/live/engine/state",
        application.projectName().get(), application.hasActiveEngine().get());
}

function exit() {}
