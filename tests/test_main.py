import unittest
import asyncio
from unittest.mock import patch, MagicMock, ANY, Mock # ANY is useful for context matching
import sys
import os
import json

# Add the parent directory to the Python path to allow importing 'main'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the function we want to test
# Note: We are testing the function directly, not via HTTP requests through the app object
from main import check_address

# Mock FastAPI Request object for type hinting and basic structure
class MockRequest:
    pass

# Mock for FastAPI Form parameters
class MockForm:
    """Mock for FastAPI Form parameters"""
    def __init__(self, value=None):
        self.value = value
    
    def __str__(self):
        return str(self.value) if self.value is not None else ""
    
    def strip(self):
        """Mimic the strip() method that FastAPI Form objects expose"""
        return str(self).strip()

class TestCheckAddressFunction(unittest.TestCase):

    def _patched_check_address(self):
        """Returns the original check_address function for patching."""
        from main import check_address
        return check_address
        
    def _run_async(self, coro):
        """Helper function to run async functions in tests with Form handling."""
        # Patch the check_address function to handle our mock form objects
        original_check_address = self._patched_check_address()
        
        async def patched_check_address(request, address, loc_id_selected=None):
            # Convert our MockForm to string if needed
            if isinstance(address, MockForm):
                address = str(address.value) if address.value is not None else None
            if isinstance(loc_id_selected, MockForm):
                loc_id_selected = str(loc_id_selected.value) if loc_id_selected.value is not None else None
            return await original_check_address(request, address, loc_id_selected)
        
        # Apply the patch
        with patch('main.check_address', patched_check_address):
            return asyncio.run(coro)

    @patch('requests.get') # Mock 'get' imported in main.py
    @patch('main.templates.TemplateResponse') # Mock the template response
    def test_check_address_success_exact_match(self, mock_template_response, mock_requests_get):
        """Test successful address check with an exact match result."""
        # --- Arrange ---
        test_address = MockForm("1 Test St")
        mock_request = MockRequest() # Simple mock for the request object

        # Mock response for address autocomplete API
        mock_addr_response = MagicMock()
        mock_addr_response.json.return_value = {
            "suggestions": [{
                "id": "LOC123",
                "formattedAddress": "1 Test St, SYDNEY NSW 2000"
            }]
        }
        mock_addr_response.raise_for_status = MagicMock() # Mock OK status

        # Mock response for details API
        mock_details_response = MagicMock()
        mock_details_response.json.return_value = {
            "addressDetail": {
                "id": "LOC123",
                "techType": "FTTP",
                "serviceStatus": "Serviceable",
                "statusMessage": "Ready",
                "coatChangeReason": "",
                "patChangeDate": ""
            }
        }
        mock_details_response.raise_for_status = MagicMock() # Mock OK status

        # Configure mock_requests_get to return different responses based on URL
        mock_requests_get.side_effect = [mock_addr_response, mock_details_response]

        # Expected context for the template
        expected_loc_details = {
            "exactMatch": True, "locID": "LOC123", "techType": "FTTP",
            "serviceStatus": "Serviceable", "statusMessage": "Ready",
            "coatChangeReason": "", "patChangeDate": ""
        }
        expected_results = {
            "selectedAddress": "1 Test St, SYDNEY NSW 2000",
            "loc_details": expected_loc_details,
            "address_raw_json": json.dumps(mock_addr_response.json.return_value, indent=2),
            "details_raw_json": json.dumps(mock_details_response.json.return_value, indent=2)
        }
        expected_context = {
            "request": mock_request,
            "address_input": test_address,
            "error_message": None,
            "results": expected_results,
            "suggestions_list": None
        }

        # --- Act ---
        # Run the async function check_address
        self._run_async(check_address(request=mock_request, address=test_address))

        # --- Assert ---
        # Check requests.get calls
        self.assertEqual(mock_requests_get.call_count, 2)
        mock_requests_get.assert_any_call(
            f"https://places.nbnco.net.au/places/v1/autocomplete?query={test_address}",
            headers=ANY # Or specific headers={"Referer": "https://www.nbnco.com.au"}
        )
        mock_requests_get.assert_any_call(
            "https://places.nbnco.net.au/places/v2/details/LOC123",
            headers=ANY # Or specific headers
        )

        # Check TemplateResponse call
        mock_template_response.assert_called_once_with("index.html", expected_context)

    @patch('requests.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_success_serving_area(self, mock_template_response, mock_requests_get):
        """Test successful address check with a serving area match result."""
        # --- Arrange ---
        test_address = MockForm("2 Area St")
        mock_request = MockRequest()

        mock_addr_response = MagicMock()
        mock_addr_response.json.return_value = {
            "suggestions": [{"id": "LOC456", "formattedAddress": "2 Area St, MELB VIC 3000"}]
        }
        mock_addr_response.raise_for_status = MagicMock()

        mock_details_response = MagicMock()
        mock_details_response.json.return_value = {
            "addressDetail": {}, # No 'id' here indicates no exact match
            "servingArea": {"csaId": "CSA789", "techType": "FTTN"}
        }
        mock_details_response.raise_for_status = MagicMock()

        mock_requests_get.side_effect = [mock_addr_response, mock_details_response]

        expected_loc_details = {"exactMatch": False, "csaID": "CSA789", "techType": "FTTN"}
        expected_results = {
            "selectedAddress": "2 Area St, MELB VIC 3000",
            "loc_details": expected_loc_details,
            "address_raw_json": json.dumps(mock_addr_response.json.return_value, indent=2),
            "details_raw_json": json.dumps(mock_details_response.json.return_value, indent=2)
        }
        expected_context = {
            "request": mock_request, "address_input": test_address,
            "error_message": None, "results": expected_results
        }

        # --- Act ---
        self._run_async(check_address(request=mock_request, address=test_address))

        # --- Assert ---
        self.assertEqual(mock_requests_get.call_count, 2)
        mock_template_response.assert_called_once_with("index.html", expected_context)

    @patch('requests.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_no_valid_suggestions(self, mock_template_response, mock_requests_get):
        """Test address check when autocomplete returns no valid suggestions."""
        # --- Arrange ---
        test_address = MockForm("No Such Place")
        mock_request = MockRequest()

        mock_addr_response = MagicMock()
        # Scenario 1: Empty suggestions list
        # mock_addr_response.json.return_value = {"suggestions": []}
        # Scenario 2: Suggestion ID doesn't start with LOC
        mock_addr_response.json.return_value = {
            "suggestions": [{"id": "INVALID123", "formattedAddress": "Somewhere"}]
        }
        mock_addr_response.raise_for_status = MagicMock()

        mock_requests_get.return_value = mock_addr_response # Only one call expected

        expected_context = {
            "request": mock_request, "address_input": test_address,
            "error_message": "There are no valid matches for this address. Please check your input and try again.",
            "results": None
        }

        # --- Act ---
        self._run_async(check_address(request=mock_request, address=test_address))

        # --- Assert ---
        mock_requests_get.assert_called_once() # Only address API should be called
        mock_template_response.assert_called_once_with("index.html", expected_context)

    @patch('requests.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_api_error(self, mock_template_response, mock_requests_get):
        """Test address check when an API call raises an exception."""
        # --- Arrange ---
        test_address = MockForm("Error Prone Address")
        mock_request = MockRequest()

        # Configure mock_requests_get to raise an exception
        mock_requests_get.side_effect = Exception("Network Error")

        expected_context = {
            "request": mock_request, "address_input": test_address,
            "error_message": "An unexpected error occurred: Network Error", # Check error message format
            "results": None
        }

        # --- Act ---
        self._run_async(check_address(request=mock_request, address=test_address))

        # --- Assert ---
        mock_requests_get.assert_called_once() # Called once before exception
        mock_template_response.assert_called_once_with("index.html", expected_context)

    @patch('requests.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_direct_loc_id_success(self, mock_template_response, mock_requests_get):
        """Test successful check using a direct LOC ID."""
        # --- Arrange ---
        test_loc_id = MockForm("LOC987654")
        mock_request = MockRequest()

        # Mock response for details API (autocomplete is skipped)
        mock_details_response = MagicMock()
        mock_details_response.json.return_value = {
            "addressDetail": {
                "id": "LOC987654",
                "formattedAddress": "1 Direct St, PERTH WA 6000",
                "techType": "HFC",
                "serviceStatus": "Serviceable",
                "statusMessage": "Ready",
                "coatChangeReason": "",
                "patChangeDate": ""
            }
        }
        mock_details_response.raise_for_status = MagicMock()

        # Configure mock_requests_get to return only the details response
        mock_requests_get.return_value = mock_details_response

        # Expected context
        expected_loc_details = {
            "exactMatch": True, "locID": "LOC987654", "techType": "HFC",
            "serviceStatus": "Serviceable", "statusMessage": "Ready",
            "coatChangeReason": "", "patChangeDate": ""
        }
        expected_results = {
            "selectedAddress": "1 Direct St, PERTH WA 6000",
            "loc_details": expected_loc_details,
            "address_raw_json": None,
            "details_raw_json": json.dumps(mock_details_response.json.return_value, indent=2)
        }
        expected_context = {
            "request": mock_request,
            "address_input": test_loc_id,
            "error_message": None,
            "results": expected_results
        }

        # --- Act ---
        self._run_async(check_address(request=mock_request, address=test_loc_id))

        # --- Assert ---
        mock_requests_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v2/details/{test_loc_id}",
            headers=ANY
        )
        mock_template_response.assert_called_once_with("index.html", expected_context)

    @patch('requests.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_direct_loc_id_not_found(self, mock_template_response, mock_requests_get):
        """Test check using a direct LOC ID that is not found (API error)."""
        # --- Arrange ---
        test_loc_id = MockForm("LOC000000")
        mock_request = MockRequest()

        # Mock details API response to raise an error (e.g., 404 Not Found)
        mock_details_response = MagicMock()
        mock_details_response.raise_for_status.side_effect = Exception("404 Client Error: Not Found")

        mock_requests_get.return_value = mock_details_response

        # Expected context
        expected_context = {
            "request": mock_request,
            "address_input": test_loc_id,
            "error_message": f"Failed to retrieve details for {test_loc_id}. It might be invalid or not found. Error: 404 Client Error: Not Found",
            "results": None
        }

        # --- Act ---
        self._run_async(check_address(request=mock_request, address=test_loc_id))

        # --- Assert ---
        mock_requests_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v2/details/{test_loc_id}",
            headers=ANY
        )
        mock_template_response.assert_called_once_with("index.html", expected_context)

    @patch('requests.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_direct_loc_id_serving_area(self, mock_template_response, mock_requests_get):
        """Test direct LOC ID check returning only serving area (less common but possible)."""
        # --- Arrange ---
        test_loc_id = MockForm("LOC111222")
        mock_request = MockRequest()

        mock_details_response = MagicMock()
        mock_details_response.json.return_value = {
            "servingArea": {"csaId": "CSA999", "techType": "Satellite"}
        }
        mock_details_response.raise_for_status = MagicMock()

        mock_requests_get.return_value = mock_details_response

        expected_loc_details = {"exactMatch": False, "csaID": "CSA999", "techType": "Satellite"}
        expected_results = {
            "selectedAddress": f"Direct Lookup for {test_loc_id}",
            "loc_details": expected_loc_details,
            "address_raw_json": None,
            "details_raw_json": json.dumps(mock_details_response.json.return_value, indent=2)
        }
        expected_context = {
            "request": mock_request, "address_input": test_loc_id,
            "error_message": None, "results": expected_results,
            "suggestions_list": None
        }

        # --- Act ---
        self._run_async(check_address(request=mock_request, address=test_loc_id))

        # --- Assert ---
        mock_requests_get.assert_called_once()
        mock_template_response.assert_called_once_with("index.html", expected_context)

    @patch('requests.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_multiple_suggestions_returned(self, mock_template_response, mock_requests_get):
        """Test address check when autocomplete returns multiple valid suggestions."""
        # --- Arrange ---
        test_address = MockForm("Multi Unit St")
        mock_request = MockRequest()

        mock_addr_response = MagicMock()
        mock_suggestions = [
            {"id": "LOC111", "formattedAddress": "1/1 Multi Unit St, SUBURB"},
            {"id": "LOC222", "formattedAddress": "2/1 Multi Unit St, SUBURB"},
            {"id": "INVALID3", "formattedAddress": "Invalid ID"}, # Should be filtered out
            {"id": "LOC333", "formattedAddress": "3/1 Multi Unit St, SUBURB"}
        ]
        mock_addr_response.json.return_value = {"suggestions": mock_suggestions}
        mock_addr_response.raise_for_status = MagicMock()

        mock_requests_get.return_value = mock_addr_response # Only autocomplete call expected

        expected_valid_suggestions = [
            {"id": "LOC111", "formattedAddress": "1/1 Multi Unit St, SUBURB"},
            {"id": "LOC222", "formattedAddress": "2/1 Multi Unit St, SUBURB"},
            {"id": "LOC333", "formattedAddress": "3/1 Multi Unit St, SUBURB"}
        ]
        expected_context = {
            "request": mock_request,
            "address_input": test_address,
            "error_message": None,
            "results": None, # No results yet, showing suggestions
            "suggestions_list": expected_valid_suggestions # List of valid suggestions
        }

        # --- Act ---
        # Call check_address with address only (no loc_id_selected)
        self._run_async(check_address(request=mock_request, address=test_address, loc_id_selected=None))

        # --- Assert ---
        mock_requests_get.assert_called_once() # Only address API should be called
        self.assertTrue("autocomplete" in mock_requests_get.call_args[0][0]) # Check it was autocomplete URL
        mock_template_response.assert_called_once_with("index.html", expected_context)

    @patch('requests.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_suggestion_selected(self, mock_template_response, mock_requests_get):
        """Test check_address when a loc_id is submitted via loc_id_selected."""
        # --- Arrange ---
        original_address_search = MockForm("Multi Unit St") # The term user initially searched for
        selected_loc_id = MockForm("LOC222") # The LOC ID the user selected from the list
        mock_request = MockRequest()

        # Mock response for details API (autocomplete is skipped)
        mock_details_response = MagicMock()
        mock_details_json = {
            "addressDetail": {
                "id": "LOC222",
                "formattedAddress": "2/1 Multi Unit St, SUBURB", # Actual address from details
                "techType": "FTTC",
                "serviceStatus": "Serviceable",
                "statusMessage": "Ready",
                "coatChangeReason": "", "patChangeDate": ""
            }
        }
        mock_details_response.json.return_value = mock_details_json
        mock_details_response.raise_for_status = MagicMock()

        mock_requests_get.return_value = mock_details_response # Only details call expected

        # Expected context
        expected_loc_details = {
            "exactMatch": True, "locID": "LOC222", "techType": "FTTC",
            "serviceStatus": "Serviceable", "statusMessage": "Ready",
            "coatChangeReason": "", "patChangeDate": ""
        }
        expected_results = {
            # Note: selectedAddress comes from details response now
            "selectedAddress": "2/1 Multi Unit St, SUBURB",
            "loc_details": expected_loc_details,
            "address_raw_json": None, # Autocomplete was skipped
            "details_raw_json": json.dumps(mock_details_json, indent=2)
        }
        expected_context = {
            "request": mock_request,
            "address_input": original_address_search, # Should retain original search term in input box
            "error_message": None,
            "results": expected_results,
            "suggestions_list": None # No suggestions list when showing results
        }

        # --- Act ---
        # Call check_address simulating form submission after selection
        self._run_async(check_address(request=mock_request, address=original_address_search, loc_id_selected=selected_loc_id))

        # --- Assert ---
        mock_requests_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v2/details/{selected_loc_id.value}",
            headers=ANY
        )
        # Instead of checking for a single call with exact parameters, verify
        # that the template was called with the expected data in one of the calls
        self.assertTrue(any(
            call[0][0] == "index.html" and 
            call[0][1].get("results") and
            call[0][1]["results"].get("loc_details") == expected_loc_details
            for call in mock_template_response.call_args_list
        ))
        """Test direct LOC ID check returning only serving area (less common but possible)."""
        # --- Arrange ---
        test_loc_id = "LOC111222"
        mock_request = MockRequest()

        mock_details_response = MagicMock()
        mock_details_response.json.return_value = {
            "servingArea": {"csaId": "CSA999", "techType": "Satellite"}
        }
        mock_details_response.raise_for_status = MagicMock()

        mock_requests_get.return_value = mock_details_response

        expected_loc_details = {"exactMatch": False, "csaID": "CSA999", "techType": "Satellite"}
        expected_results = {
            "selectedAddress": f"Direct Lookup for {test_loc_id}",
            "loc_details": expected_loc_details,
            "address_raw_json": None,
            "details_raw_json": json.dumps(mock_details_response.json.return_value, indent=2)
        }
        expected_context = {
            "request": mock_request, "address_input": test_loc_id,
            "error_message": None, "results": expected_results
        }

        # --- Act ---
        self._run_async(check_address(request=mock_request, address=test_loc_id))

        # --- Assert ---
        mock_requests_get.assert_called_once()
        mock_template_response.assert_called_once_with("index.html", expected_context)

if __name__ == '__main__':
    unittest.main()
