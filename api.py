#!/usr/bin/env python3
from requests import get


def nbnQueryAddress(address: str) -> dict:
    # Empty dict to store results
    results = {}

    # Poke the NBN autocomplete API with the supplied address to check
    apiUrl = f"https://places.nbnco.net.au/places/v1/autocomplete?query={address}"
    apiResponse = get(apiUrl, headers={"Referer": "https://www.nbnco.com.au"}).json()

    # Check if 'suggestions' key exists and is not empty
    if "suggestions" in apiResponse and len(apiResponse["suggestions"]) > 0:
        # Always take the first suggestion for simplicity in the web UI
        first_suggestion = apiResponse["suggestions"][0]
        loc_id = first_suggestion["id"]
        # Check if the locID starts with "LOC"
        if loc_id.startswith("LOC"):
            results["validResult"] = True
            results["selectedAddress"] = first_suggestion["formattedAddress"]
            results["locID"] = loc_id
        else:
            # Invalid locID format
            results["validResult"] = False
            results["selectedAddress"] = None
            results["locID"] = None
    else:
        # No suggestions are given, return False for validResult
        results["validResult"] = False
        results["selectedAddress"] = None
        results["locID"] = None

    return results


def nbnLocDetails(locID: str) -> dict:
    # Empty dict to store results
    results = {}

    # Poke the NBN details API with the retrieved location ID
    apiUrl = f"https://places.nbnco.net.au/places/v2/details/{locID}"
    apiResponse = get(apiUrl, headers={"Referer": "https://www.nbnco.com.au"}).json()

    # Check for an NBN LOC ID in the response
    if "id" in apiResponse["addressDetail"]:
        # An NBN LOC ID is present, return the address details
        results["exactMatch"] = True
        results["locID"] = apiResponse["addressDetail"]["id"]
        results["techType"] = apiResponse["addressDetail"]["techType"]
        results["serviceStatus"] = apiResponse["addressDetail"]["serviceStatus"]
        # This API sucks and only returns this field sometimes, so we have to check for it
        if "statusMessage" in apiResponse["addressDetail"]:
            results["statusMessage"] = apiResponse["addressDetail"]["statusMessage"]
        else:
            results["statusMessage"] = ""
        results["coatChangeReason"] = apiResponse["addressDetail"]["coatChangeReason"]
        if results["coatChangeReason"] != "":
            results["patChangeDate"] = apiResponse["addressDetail"]["patChangeDate"]
        else:
            results["patChangeDate"] = ""
    else:
        # No NBN LOC ID is present, return a warning and the serving area details
        results["exactMatch"] = False
        results["csaID"] = apiResponse["servingArea"]["csaId"]
        results["techType"] = apiResponse["servingArea"]["techType"]
    return results
