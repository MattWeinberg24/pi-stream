// API operation frontend tool

const OPERATIONS = [
    "janus/start",
    "janus/stop",
    "audio/start",
    "audio/stop",
    "set_format",
    "get_format",
    "fast_screenshot/start",
    "fast_screenshot/stop",
    "status",
    "janus/force_stop",
    "janus/force_exists",
    "audio/force_stop",
    "audio/force_exists",
    "reset_usb"
];


document.addEventListener("DOMContentLoaded", () => {
    const api_operations = document.getElementById("api-operations");

    OPERATIONS.forEach((op) => {
        const btn = document.createElement("button");
        btn.textContent = op;

        btn.addEventListener("click",() => {
            const url = window.location.origin + "/" + op;
            
            // parse request body
            const bodyString = document.getElementById("request-body").value;
            let body = {}
            try {
                body = JSON.parse(bodyString);
            } 
            catch (error) {
                console.log("No Request Body");
            }
            console.log(body);

            //send request
            console.log(`Fetching ${url}`);
            fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(body)
            }).then(response => response.json()).then(data => {
                //handle response
                if (data.success != undefined && !data.success) {
                    console.error(data)
                }
                else {
                    console.log(data);
                }
            }).catch(e => {
                console.error(e);
            });
        });

        api_operations.appendChild(btn);
    });
});
