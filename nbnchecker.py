#! /usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests==2.32.3",
# ]
# ///
import sys
import os
from requests import get


def main():
    checkAddress = input("Enter address to check: ")
    # Run the nbnCheck function with the address as an input
    addressQueryResult = nbnQueryAddress(checkAddress)
    # Print an error if no valid suggestions are returned
    if addressQueryResult["validResult"] is False:
        print(
            "\nThere are no matches for this address. Please check your input and try again.\n"
        )
        return
    else:
        # Print the formatted address for the selected address
        print("\nYour selected address is: ", addressQueryResult["selectedAddress"])

    # Get the details for the returned location ID
    locQueryResult = nbnLocDetails(addressQueryResult["locID"])
    if locQueryResult["exactMatch"] is True:
        # Exact match to an NBN LOC ID, print the specifics for that match
        print("\nLOC ID: ", locQueryResult["locID"])
        print("Service Status: ", locQueryResult["serviceStatus"])
        if locQueryResult["statusMessage"] == "connected-true":
            print("An AVC is active at this LOC ID!")
        if locQueryResult["statusMessage"] == "connected":
            print("This LOC ID is ready for remote AVC provisioning!")
        if locQueryResult["coatChangeReason"] == "on-demand":
            print(
                "On-Demand Fibre Upgrade is available for this LOC ID from",
                locQueryResult["patChangeDate"],
                "!",
            )
    else:
        # No exact match to an NBN LOC ID, print the serving area details
        print(
            "\nThere is no exact match in the NBN database for your selected address."
        )
        print("Serving Area details are as follows.")
        print("\nCSA ID: ", locQueryResult["csaID"])
    print("Technology Type: ", locQueryResult["techType"])
    print("\n")


def nbnQueryAddress(address: str) -> dict:
    # Empty dict to store results
    results = {}

    # Poke the NBN autocomplete API with the supplied address to check
    apiUrl = f"https://places.nbnco.net.au/places/v1/autocomplete?query={address}"
    apiResponse = get(apiUrl, headers={"Referer": "https://www.nbnco.com.au"}).json()

    if len(apiResponse["suggestions"]) > 0:
        # We have at least one valid address suggestion
        results["validResult"] = True
        if len(apiResponse["suggestions"]) != 1:
            # More than one suggestion is given, display a list and ask for selection
            suggestionsList = apiResponse["suggestions"]
            # Generate a list of suggested addresses
            print("\nPlease choose your address from the list below: ")
            for n, address in enumerate(suggestionsList):
                print(f"{n}: ", address["formattedAddress"])
            selectedAddressNum = int(input("\nSelection: "))
            # Once a suggestion is selected, return the address and LOC ID
            results["selectedAddress"] = suggestionsList[selectedAddressNum][
                "formattedAddress"
            ]
            results["locID"] = suggestionsList[selectedAddressNum]["id"]
        else:
            # Only one suggestion is given, return the address and LOC ID immediately
            results["selectedAddress"] = apiResponse["suggestions"][0][
                "formattedAddress"
            ]
            results["locID"] = apiResponse["suggestions"][0]["id"]
    else:
        # No suggestions are given, return False for validResult
        results["validResult"] = False
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


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye!")
        try:
            sys.exit(1)
        except SystemExit:
            os._exit(1)
