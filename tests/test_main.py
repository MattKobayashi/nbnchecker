import unittest
import asyncio
from unittest.mock import patch, MagicMock, ANY # ANY is useful for context matching
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

class TestCheckAddressFunction(unittest.TestCase):

    def _run_async(self, coro):
        """Helper function to run async functions in tests."""
        return asyncio.run(coro)

    @patch('main.get') # Mock 'get' imported in main.py
    @patch('main.templates.TemplateResponse') # Mock the template response
    def test_check_address_success_exact_match(self, mock_template_response, mock_requests_get):
        """Test successful address check with an exact match result."""
        # --- Arrange ---
        test_address = "1 Test St"
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
            "results": expected_results
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

    @patch('main.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_success_serving_area(self, mock_template_response, mock_requests_get):
        """Test successful address check with a serving area match result."""
        # --- Arrange ---
        test_address = "2 Area St"
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

    @patch('main.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_no_valid_suggestions(self, mock_template_response, mock_requests_get):
        """Test address check when autocomplete returns no valid suggestions."""
        # --- Arrange ---
        test_address = "No Such Place"
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

    @patch('main.get')
    @patch('main.templates.TemplateResponse')
    def test_check_address_api_error(self, mock_template_response, mock_requests_get):
        """Test address check when an API call raises an exception."""
        # --- Arrange ---
        test_address = "Error Prone Address"
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

if __name__ == '__main__':
    unittest.main()
