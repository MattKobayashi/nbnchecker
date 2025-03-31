import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Import the refactored functions from nbnchecker
from nbnchecker import nbnQueryAddress, nbnLocDetails

app = FastAPI()

# Configure templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Renders the initial form page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/", response_class=HTMLResponse)
async def check_address(request: Request, address: str = Form(...)):
    """Handles form submission, calls NBN checker functions, and renders results."""
    context = {"request": request, "address_input": address}
    error_message = None
    results_data = None

    try:
        # Step 1: Query the address
        address_query_result = nbnQueryAddress(address)

        if not address_query_result["validResult"]:
            error_message = "There are no matches for this address. Please check your input and try again."
        else:
            # Step 2: Get location details using the locID from the first result
            loc_id = address_query_result["locID"]
            loc_details_result = nbnLocDetails(loc_id)

            # Prepare results for the template
            results_data = {
                "selectedAddress": address_query_result["selectedAddress"],
                "loc_details": loc_details_result
            }

    except Exception as e:
        # Basic error handling for API calls or other issues
        print(f"An error occurred: {e}") # Log error to console
        error_message = "An unexpected error occurred while checking the address."

    context["error_message"] = error_message
    context["results"] = results_data

    return templates.TemplateResponse("index.html", context)

if __name__ == "__main__":
    # Run the FastAPI app using uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
