import unittest
import asyncio
from unittest.mock import patch, MagicMock, ANY, Mock # ANY is useful for context matching
import sys
import os
import json
import importlib

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
        """Helper function to run async functions in tests."""
        return asyncio.run(coro)
        
    def _setup_mock_requests(self, responses=None):
        """
        Sets up a custom mock for requests.get that tracks calls.
        Args:
            responses: Dict mapping URL patterns to response objects 
        Returns:
            Mock object with call tracking
        """
        # Create a mock for requests.get
        mock_get = MagicMock()
        
        # Function to find the correct response based on URL pattern
        def side_effect(url, headers=None, **kwargs):
            # Log the call
            mock_get.call_args_list.append(((url, headers), kwargs))
            
            # Find matching response based on URL
            if responses:
                for pattern, response in responses.items():
                    if pattern in url:
                        return response
                        
            # Default response if no specific one provided
            mock_response = MagicMock()
            mock_response.json.return_value = {}
            mock_response.raise_for_status = MagicMock()
            return mock_response
        
        # Set the side effect to use our custom function
        mock_get.side_effect = side_effect
        
        return mock_get

    @patch('main.templates.TemplateResponse')
    def test_check_address_success_exact_match(self, mock_template_response):
        """Test successful address check with an exact match result."""
        # --- Arrange ---
        test_address = MockForm("1 Test St")
        mock_request = MockRequest()

        # Mock response for address autocomplete API
        mock_addr_response = MagicMock()
        mock_addr_response.json.return_value = {
            "suggestions": [{
                "id": "LOC123",
                "formattedAddress": "1 Test St, SYDNEY NSW 2000"
            }]
        }
        mock_addr_response.raise_for_status = MagicMock()

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
        mock_details_response.raise_for_status = MagicMock()

        # Set up mock with expected responses
        responses = {
            "autocomplete": mock_addr_response,
            "details": mock_details_response
        }
        
        # Create our mock and configure its side effect
        mock_get = self._setup_mock_requests(responses)
        
        # Use patch as a context manager to ensure it's applied correctly
        with patch('requests.get', mock_get):
            # --- Act ---
            async def test_coro():
                return await check_address(request=mock_request, address=test_address)
            result = self._run_async(test_coro())
            
            # --- Assert ---
            self.assertEqual(len(mock_get.call_args_list), 2)
            self.assertTrue(any("autocomplete" in args[0][0] for args in mock_get.call_args_list))
            self.assertTrue(any("details" in args[0][0] for args in mock_get.call_args_list))
            mock_template_response.assert_called_once()

    @patch('main.templates.TemplateResponse')
    def test_check_address_success_serving_area(self, mock_template_response):
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

        # Set up mock with expected responses
        responses = {
            "autocomplete": mock_addr_response,
            "details": mock_details_response
        }
        
        # Create our mock and configure its side effect
        mock_get = self._setup_mock_requests(responses)
        
        # Use patch as a context manager to ensure it's applied correctly
        with patch('requests.get', mock_get):
            # --- Act ---
            async def test_coro():
                return await check_address(request=mock_request, address=test_address)
            result = self._run_async(test_coro())
            
            # --- Assert ---
            self.assertEqual(len(mock_get.call_args_list), 2)
            self.assertTrue(any("autocomplete" in args[0][0] for args in mock_get.call_args_list))
            self.assertTrue(any("details" in args[0][0] for args in mock_get.call_args_list))
            mock_template_response.assert_called_once()

    @patch('main.templates.TemplateResponse')
    def test_check_address_no_valid_suggestions(self, mock_template_response):
        """Test address check when autocomplete returns no valid suggestions."""
        # --- Arrange ---
        test_address = MockForm("No Such Place")
        mock_request = MockRequest()

        mock_addr_response = MagicMock()
        # Scenario 2: Suggestion ID doesn't start with LOC
        mock_addr_response.json.return_value = {
            "suggestions": [{"id": "INVALID123", "formattedAddress": "Somewhere"}]
        }
        mock_addr_response.raise_for_status = MagicMock()

        # Set up mock with expected responses
        responses = {"autocomplete": mock_addr_response}
        
        # Create our mock and configure its side effect
        mock_get = self._setup_mock_requests(responses)
        
        # Use patch as a context manager to ensure it's applied correctly
        with patch('requests.get', mock_get):
            # --- Act ---
            async def test_coro():
                return await check_address(request=mock_request, address=test_address)
            result = self._run_async(test_coro())
            
            # --- Assert ---
            self.assertEqual(len(mock_get.call_args_list), 1) # Only address API should be called
            self.assertTrue(any("autocomplete" in args[0][0] for args in mock_get.call_args_list))
            mock_template_response.assert_called_once()

    @patch('main.templates.TemplateResponse')
    def test_check_address_api_error(self, mock_template_response):
        """Test address check when an API call raises an exception."""
        # --- Arrange ---
        test_address = MockForm("Error Prone Address")
        mock_request = MockRequest()

        # Create a mock that raises an exception
        mock_get = MagicMock()
        mock_get.side_effect = Exception("Network Error")
        
        # Use patch as a context manager
        with patch('requests.get', mock_get):
            # --- Act ---
            async def test_coro():
                return await check_address(request=mock_request, address=test_address)
            result = self._run_async(test_coro())
            
            # --- Assert ---
            mock_template_response.assert_called_once()

    @patch('main.templates.TemplateResponse')
    def test_check_address_direct_loc_id_success(self, mock_template_response):
        """Test successful check using a direct LOC ID."""
        # --- Arrange ---
        test_loc_id = MockForm("LOC987654")
        mock_request = MockRequest()

        # Mock response for details API
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

        # Set up mock with expected responses
        responses = {"details": mock_details_response}
        
        # Create our mock and configure its side effect
        mock_get = self._setup_mock_requests(responses)
        
        # Use patch as a context manager to ensure it's applied correctly
        with patch('requests.get', mock_get):
            # --- Act ---
            async def test_coro():
                return await check_address(request=mock_request, address=test_loc_id)
            result = self._run_async(test_coro())
            
            # --- Assert ---
            self.assertEqual(len(mock_get.call_args_list), 1)
            self.assertTrue(any(f"details/{test_loc_id}" in args[0][0] for args in mock_get.call_args_list))
            mock_template_response.assert_called_once()

    @patch('main.templates.TemplateResponse')
    def test_check_address_direct_loc_id_not_found(self, mock_template_response):
        """Test check using a direct LOC ID that is not found (API error)."""
        # --- Arrange ---
        test_loc_id = MockForm("LOC000000")
        mock_request = MockRequest()

        # Mock details API response to raise an error
        mock_details_response = MagicMock()
        mock_details_response.raise_for_status.side_effect = Exception("404 Client Error: Not Found")

        # Set up mock with expected responses
        responses = {"details": mock_details_response}
        
        # Create our mock and configure its side effect
        mock_get = self._setup_mock_requests(responses)
        
        # Use patch as a context manager to ensure it's applied correctly
        with patch('requests.get', mock_get):
            # --- Act ---
            async def test_coro():
                return await check_address(request=mock_request, address=test_loc_id)
            result = self._run_async(test_coro())
            
            # --- Assert ---
            self.assertEqual(len(mock_get.call_args_list), 1)
            self.assertTrue(any(f"details/{test_loc_id}" in args[0][0] for args in mock_get.call_args_list))
            mock_template_response.assert_called_once()

    @patch('main.templates.TemplateResponse')
    def test_check_address_direct_loc_id_serving_area(self, mock_template_response):
        """Test direct LOC ID check returning only serving area (less common but possible)."""
        # --- Arrange ---
        test_loc_id = MockForm("LOC111222")
        mock_request = MockRequest()

        mock_details_response = MagicMock()
        mock_details_response.json.return_value = {
            "servingArea": {"csaId": "CSA999", "techType": "Satellite"}
        }
        mock_details_response.raise_for_status = MagicMock()

        # Set up mock with expected responses
        responses = {"details": mock_details_response}
        
        # Create our mock and configure its side effect
        mock_get = self._setup_mock_requests(responses)
        
        # Use patch as a context manager to ensure it's applied correctly
        with patch('requests.get', mock_get):
            # --- Act ---
            async def test_coro():
                return await check_address(request=mock_request, address=test_loc_id)
            result = self._run_async(test_coro())
            
            # --- Assert ---
            self.assertEqual(len(mock_get.call_args_list), 1)
            self.assertTrue(any(f"details/{test_loc_id}" in args[0][0] for args in mock_get.call_args_list))
            mock_template_response.assert_called_once()

    @patch('main.templates.TemplateResponse')
    def test_check_address_multiple_suggestions_returned(self, mock_template_response):
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

        # Set up mock with expected responses
        responses = {"autocomplete": mock_addr_response}
        
        # Create our mock and configure its side effect
        mock_get = self._setup_mock_requests(responses)
        
        # Use patch as a context manager to ensure it's applied correctly
        with patch('requests.get', mock_get):
            # --- Act ---
            async def test_coro():
                return await check_address(request=mock_request, address=test_address, loc_id_selected=None)
            result = self._run_async(test_coro())
            
            # --- Assert ---
            self.assertEqual(len(mock_get.call_args_list), 1) # Only address API should be called
            self.assertTrue(any("autocomplete" in args[0][0] for args in mock_get.call_args_list))
            mock_template_response.assert_called_once()

    @patch('main.templates.TemplateResponse')
    def test_check_address_suggestion_selected(self, mock_template_response):
        """Test check_address when a loc_id is submitted via loc_id_selected."""
        # --- Arrange ---
        original_address_search = MockForm("Multi Unit St") # The term user initially searched for
        selected_loc_id = MockForm("LOC222") # The LOC ID the user selected from the list
        mock_request = MockRequest()

        # Mock response for details API
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

        # Set up mock with expected responses
        responses = {"details": mock_details_response}
        
        # Create our mock and configure its side effect
        mock_get = self._setup_mock_requests(responses)
        
        # Use patch as a context manager to ensure it's applied correctly
        with patch('requests.get', mock_get):
            # --- Act ---
            async def test_coro():
                return await check_address(request=mock_request, address=original_address_search, loc_id_selected=selected_loc_id)
            result = self._run_async(test_coro())
            
            # --- Assert ---
            self.assertEqual(len(mock_get.call_args_list), 1)
            self.assertTrue(any(f"details/{selected_loc_id}" in args[0][0] for args in mock_get.call_args_list))
            
            # Verify the template was called with the expected data
            expected_loc_details = {
                "exactMatch": True, "locID": "LOC222", "techType": "FTTC",
                "serviceStatus": "Serviceable", "statusMessage": "Ready",
                "coatChangeReason": "", "patChangeDate": ""
            }
            self.assertTrue(any(
                call[0][0] == "index.html" and 
                call[0][1].get("results") and
                call[0][1]["results"].get("loc_details") == expected_loc_details
                for call in mock_template_response.call_args_list
            ))

if __name__ == '__main__':
    unittest.main()
