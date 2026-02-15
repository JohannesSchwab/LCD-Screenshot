// Perform background initialization
doAjax("/init", "POST");

let refreshLCDTimer = null;

function getMethods(obj) {
    var result = [];
    for (var id in obj) {
        try {
            if (typeof obj[id] == "function") {
                result.push(id + ": " + obj[id].toString());
            }
        } catch (err) {
            result.push(id + ": inaccessible");
        }
    }
    return result;
}

function refreshLCDHandler() {
    if (this.readyState !== 4 || this.status !== 200) {
        return;
    }
    if (this.responseText) {
        var response = JSON.parse(this.responseText);
        lcdContentElement = document.getElementById("lcd-screenshot-content");
        if (!lcdContentElement) {
            console.error(
                "Could not find element with id 'lcd-screenshot-content'",
            );
            return;
        }
        lcdContentElement.innerHTML = response.result;
        // lcdContentElement.querySelectorAll("svg").forEach((svg) => {
        //     svg.setAttribute("width", "100%");
        //     svg.setAttribute("height", "100%");
        // });
    }
}

function getTextInputAsLines() {
    var text = document.getElementById("text-input").value;
    var lines = text.split("\n");
    return lines;
}

function refreshLCD() {
    const duration = 500; // ms

    if (refreshLCDTimer) {
        clearTimeout(refreshLCDTimer);
    }

    refreshLCDTimer = setTimeout(function () {
        const request = {
            "input-data": getTextInputAsLines(),
        };
        doAjax("/refresh/lcd", "POST", refreshLCDHandler, request);
    }, duration);
}

function saveScreenshot() {
    doAjax(
        "/save/screenshot",
        "POST",
        function () {
            if (this.readyState !== 4 || this.status !== 200) {
                alert(
                    "Error saving screenshot " +
                        this.status +
                        ": " +
                        this.statusText,
                );
                return;
            }
            alert("Screenshot saved successfully!");
        },
        {
            "svg-data": document.getElementById("lcd-screenshot-content")
                .innerHTML,
        },
    );
}

// From https://gist.github.com/dharmavir/936328
function getHttpRequestObject() {
    // Define and initialize as false
    var xmlHttpRequst = false;

    // Mozilla/Safari/Non-IE
    if (window.XMLHttpRequest) {
        xmlHttpRequst = new XMLHttpRequest();
    }
    // IE
    else if (window.ActiveXObject) {
        xmlHttpRequst = new ActiveXObject("Microsoft.XMLHTTP");
    }
    return xmlHttpRequst;
}

// Does the AJAX call to URL specific with rest of the parameters
function doAjax(url, method, responseHandler, data) {
    // Set the variables
    url = url || "";
    method = method || "GET";
    async = true;
    data = data || {};
    data.token = window.token;

    if (url == "") {
        alert("URL can not be null/blank");
        return false;
    }
    var xmlHttpRequest = getHttpRequestObject();

    // If AJAX supported
    if (xmlHttpRequest != false) {
        xmlHttpRequest.open(method, url, async);
        // Set request header (optional if GET method is used)
        if (method == "POST") {
            xmlHttpRequest.setRequestHeader("Content-Type", "application/json");
        }
        // Assign (or define) response-handler/callback when ReadyState is changed.
        xmlHttpRequest.onreadystatechange = responseHandler;
        // Send data
        xmlHttpRequest.send(JSON.stringify(data));
    } else {
        alert("Please use browser with Ajax support.!");
    }
}
