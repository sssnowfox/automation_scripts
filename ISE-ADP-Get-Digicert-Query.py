import requests
import json

# Flexible DigiCert API Script for XSOAR

api_key = demisto.args()["APIKey"]
endpoint = demisto.args()["Endpoint"]

# Build the full URI
base_url = "https://www.digicert.com/services/v2"
uri = base_url + endpoint

# Set up headers
headers = {
    "X-DC-DEVKEY": api_key
}

try:
    # Make the API call
    response = requests.get(uri, headers=headers)
    response.raise_for_status()
    result = response.json()

    # Success - return the response
    demisto.results(
        "API Call Successful!\nEndpoint: {}\nResponse: {}".format(
            endpoint,
            json.dumps(result, indent=2)
        )
    )

except Exception as e:
    # Error - return the error message
    demisto.results("API Call Failed to: {}\nError: {}".format(uri, str(e)))
