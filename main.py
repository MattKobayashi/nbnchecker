#!/usr/bin/env python3
import uvicorn
import json
from requests import get
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
#from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Configure templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Renders the initial form page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/", response_class=HTMLResponse)
async def check_address(request: Request, address: str = Form(...)):
    """Handles form submission, calls NBN APIs directly, and renders results."""
    context = {"request": request, "address_input": address}
    error_message = None
    results_data = None
    address_raw_json = None
    details_raw_json = None
    loc_id = None
    selected_address = None
    is_loc_id_search = False

    # Clean up input
    search_input = address.strip()

    try:
        # Check if the input looks like a LOC ID
        if search_input.upper().startswith("LOC"):
            print(f"Detected LOC ID search: {search_input}")
            loc_id = search_input.upper()
            is_loc_id_search = True
            selected_address = f"Direct Lookup for {loc_id}"
        else:
            # Step 1: Query the address using autocomplete
            print(f"Performing address search for: {search_input}")
            address_api_url = f"https://places.nbnco.net.au/places/v1/autocomplete?query={search_input}"
            address_response = get(address_api_url, headers={"Referer": "https://www.nbnco.com.au"})
            address_response.raise_for_status()
            address_raw_json = address_response.json()

            valid_address_result = False
            if "suggestions" in address_raw_json and len(address_raw_json["suggestions"]) > 0:
                first_suggestion = address_raw_json["suggestions"][0]
                if first_suggestion.get("id", "").startswith("LOC"):
                    loc_id = first_suggestion["id"]
                    selected_address = first_suggestion.get("formattedAddress")
                    valid_address_result = True

            if not valid_address_result:
                error_message = "There are no valid matches for this address. Please check your input and try again."
                loc_id = None
        if loc_id:
            # Step 2: Get location details using the locID
            print(f"Fetching details for LOC ID: {loc_id}")
            details_api_url = f"https://places.nbnco.net.au/places/v2/details/{loc_id}"
            details_response = get(details_api_url, headers={"Referer": "https://www.nbnco.com.au"})
            details_response.raise_for_status()
            details_raw_json = details_response.json()

            # Process details_raw_json
            loc_details_result = {}
            if "addressDetail" in details_raw_json and "id" in details_raw_json["addressDetail"]:
                loc_details_result["exactMatch"] = True
                loc_details_result["locID"] = details_raw_json["addressDetail"]["id"]
                loc_details_result["techType"] = details_raw_json["addressDetail"].get("techType")
                loc_details_result["serviceStatus"] = details_raw_json["addressDetail"].get("serviceStatus")
                loc_details_result["statusMessage"] = details_raw_json["addressDetail"].get("statusMessage", "")
                loc_details_result["coatChangeReason"] = details_raw_json["addressDetail"].get("coatChangeReason", "")
                if loc_details_result["coatChangeReason"]:
                    loc_details_result["patChangeDate"] = details_raw_json["addressDetail"].get("patChangeDate", "")
                else:
                    loc_details_result["patChangeDate"] = ""

                # If it was a LOC ID search, try to get the formatted address from details
                if is_loc_id_search:
                    selected_address = details_raw_json["addressDetail"].get("formattedAddress", selected_address)

            elif "servingArea" in details_raw_json:
                loc_details_result["exactMatch"] = False
                loc_details_result["csaID"] = details_raw_json["servingArea"].get("csaId")
                loc_details_result["techType"] = details_raw_json["servingArea"].get("techType")
            else:
                error_message = f"Could not retrieve detailed location information for {loc_id}."
                loc_details_result = None

            # Prepare results for the template only if loc_details_result is valid
            if loc_details_result:
                results_data = {
                    "selectedAddress": selected_address,
                    "loc_details": loc_details_result,
                    "address_raw_json": json.dumps(address_raw_json, indent=2) if address_raw_json else None,
                    "details_raw_json": json.dumps(details_raw_json, indent=2) if details_raw_json else None
                }
        elif not is_loc_id_search and not error_message:
            error_message = "Failed to determine LOC ID from the provided address."

    except Exception as e:
        print(f"An error occurred: {e}")
        if is_loc_id_search:
            error_message = f"Failed to retrieve details for {loc_id}. It might be invalid or not found. Error: {e}"
        else:
            error_message = f"An unexpected error occurred: {e}"

    context["error_message"] = error_message
    context["results"] = results_data

    return templates.TemplateResponse("index.html", context)

if __name__ == "__main__":
    # Run the FastAPI app using uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
