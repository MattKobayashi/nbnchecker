import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the Python path to allow importing 'api'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api import nbnQueryAddress, nbnLocDetails

class TestNbnApiFunctions(unittest.TestCase):

    @patch('api.get')
    def test_nbnQueryAddress_success(self, mock_get):
        """Test nbnQueryAddress with a valid response and LOC ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "suggestions": [
                {
                    "id": "LOC000123456789",
                    "formattedAddress": "1 Test St, SYDNEY NSW 2000"
                }
            ]
        }
        mock_get.return_value = mock_response

        address = "1 Test St"
        result = nbnQueryAddress(address)

        mock_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v1/autocomplete?query={address}",
            headers={"Referer": "https://www.nbnco.com.au"}
        )
        self.assertTrue(result["validResult"])
        self.assertEqual(result["selectedAddress"], "1 Test St, SYDNEY NSW 2000")
        self.assertEqual(result["locID"], "LOC000123456789")

    @patch('api.get')
    def test_nbnQueryAddress_invalid_loc_id_prefix(self, mock_get):
        """Test nbnQueryAddress with a valid response but invalid LOC ID prefix."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "suggestions": [
                {
                    "id": "INVALID000123456789", # Does not start with LOC
                    "formattedAddress": "2 Invalid St, MELBOURNE VIC 3000"
                }
            ]
        }
        mock_get.return_value = mock_response

        address = "2 Invalid St"
        result = nbnQueryAddress(address)

        mock_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v1/autocomplete?query={address}",
            headers={"Referer": "https://www.nbnco.com.au"}
        )
        self.assertFalse(result["validResult"])
        self.assertIsNone(result["selectedAddress"])
        self.assertIsNone(result["locID"])

    @patch('api.get')
    def test_nbnQueryAddress_no_suggestions(self, mock_get):
        """Test nbnQueryAddress when the API returns no suggestions."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"suggestions": []}
        mock_get.return_value = mock_response

        address = "NonExistent Address 123"
        result = nbnQueryAddress(address)

        mock_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v1/autocomplete?query={address}",
            headers={"Referer": "https://www.nbnco.com.au"}
        )
        self.assertFalse(result["validResult"])
        self.assertIsNone(result["selectedAddress"])
        self.assertIsNone(result["locID"])

    @patch('api.get')
    def test_nbnQueryAddress_missing_suggestions_key(self, mock_get):
        """Test nbnQueryAddress when the API response lacks the 'suggestions' key."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"other_key": "some_value"} # No 'suggestions'
        mock_get.return_value = mock_response

        address = "Another Address"
        result = nbnQueryAddress(address)

        mock_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v1/autocomplete?query={address}",
            headers={"Referer": "https://www.nbnco.com.au"}
        )
        self.assertFalse(result["validResult"])
        self.assertIsNone(result["selectedAddress"])
        self.assertIsNone(result["locID"])

    @patch('api.get')
    def test_nbnLocDetails_exact_match_full(self, mock_get):
        """Test nbnLocDetails with an exact match and all fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "addressDetail": {
                "id": "LOC000987654321",
                "techType": "FTTP",
                "serviceStatus": "Serviceable",
                "statusMessage": "Ready to Connect",
                "coatChangeReason": "Upgrade",
                "patChangeDate": "2023-10-26"
            },
            "servingArea": {} # Included for completeness, but not used in this case
        }
        mock_get.return_value = mock_response

        loc_id = "LOC000987654321"
        result = nbnLocDetails(loc_id)

        mock_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v2/details/{loc_id}",
            headers={"Referer": "https://www.nbnco.com.au"}
        )
        self.assertTrue(result["exactMatch"])
        self.assertEqual(result["locID"], "LOC000987654321")
        self.assertEqual(result["techType"], "FTTP")
        self.assertEqual(result["serviceStatus"], "Serviceable")
        self.assertEqual(result["statusMessage"], "Ready to Connect")
        self.assertEqual(result["coatChangeReason"], "Upgrade")
        self.assertEqual(result["patChangeDate"], "2023-10-26")

    @patch('api.get')
    def test_nbnLocDetails_exact_match_minimal(self, mock_get):
        """Test nbnLocDetails with an exact match and minimal optional fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "addressDetail": {
                "id": "LOC000111222333",
                "techType": "HFC",
                "serviceStatus": "Not Serviceable",
                # "statusMessage": "Missing", # Intentionally missing
                "coatChangeReason": "", # Empty
                # "patChangeDate": "Missing" # Should not be present if coatChangeReason is empty
            },
            "servingArea": {}
        }
        mock_get.return_value = mock_response

        loc_id = "LOC000111222333"
        result = nbnLocDetails(loc_id)

        mock_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v2/details/{loc_id}",
            headers={"Referer": "https://www.nbnco.com.au"}
        )
        self.assertTrue(result["exactMatch"])
        self.assertEqual(result["locID"], "LOC000111222333")
        self.assertEqual(result["techType"], "HFC")
        self.assertEqual(result["serviceStatus"], "Not Serviceable")
        self.assertEqual(result["statusMessage"], "") # Should default to empty string
        self.assertEqual(result["coatChangeReason"], "")
        self.assertEqual(result["patChangeDate"], "") # Should default to empty string

    @patch('api.get')
    def test_nbnLocDetails_no_exact_match(self, mock_get):
        """Test nbnLocDetails when no exact match is found (serving area details)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "addressDetail": {
                # "id": "Missing" # Intentionally missing 'id' key
            },
            "servingArea": {
                "csaId": "CSA12345",
                "techType": "FTTN"
            }
        }
        mock_get.return_value = mock_response

        loc_id = "LOC000444555666"
        result = nbnLocDetails(loc_id)

        mock_get.assert_called_once_with(
            f"https://places.nbnco.net.au/places/v2/details/{loc_id}",
            headers={"Referer": "https://www.nbnco.com.au"}
        )
        self.assertFalse(result["exactMatch"])
        self.assertEqual(result["csaID"], "CSA12345")
        self.assertEqual(result["techType"], "FTTN")
        # Check that keys specific to exactMatch are not present
        self.assertNotIn("locID", result)
        self.assertNotIn("serviceStatus", result)
        self.assertNotIn("statusMessage", result)
        self.assertNotIn("coatChangeReason", result)
        self.assertNotIn("patChangeDate", result)


if __name__ == '__main__':
    unittest.main()
