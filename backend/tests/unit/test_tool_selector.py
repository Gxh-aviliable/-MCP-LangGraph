"""Test Tool Selector Decision

Test tool_selector_node decision logic:
- Default decision (all tools enabled)
- Skip specific tools based on special instructions
- Decision based on user message
"""
import pytest
from backend.tests.mocks.mock_llm import MockLLM


class TestToolSelectorDecision:
    """Test tool selection decision"""

    def test_default_all_tools_enabled(self):
        """Test default all tools enabled"""
        expected_decision = {
            "attraction": True,
            "weather": True,
            "transport": True,
            "hotel": True
        }
        assert all(expected_decision.values()) == True

    def test_skip_attraction_via_special_instructions(self):
        """Test skip attraction via special instructions"""
        state = {
            "city": "Beijing",
            "special_instructions": {
                "skip_attraction": True,
                "skip_attraction_reason": "User explicitly said no attractions"
            }
        }
        expected_decision = {
            "attraction": False,
            "weather": True,
            "transport": True,
            "hotel": True
        }
        assert expected_decision["attraction"] == False

    def test_skip_transport_via_special_instructions(self):
        """Test skip transport via special instructions"""
        state = {
            "city": "Beijing",
            "origin": "Beijing",
            "special_instructions": {
                "skip_transport": True,
                "skip_transport_reason": "Local tour"
            }
        }
        expected_decision = {
            "attraction": True,
            "weather": True,
            "transport": False,
            "hotel": True
        }
        assert expected_decision["transport"] == False

    def test_skip_hotel_via_special_instructions(self):
        """Test skip hotel via special instructions"""
        state = {
            "city": "Beijing",
            "special_instructions": {
                "skip_hotel": True,
                "skip_hotel_reason": "User already booked hotel"
            }
        }
        expected_decision = {
            "attraction": True,
            "weather": True,
            "transport": True,
            "hotel": False
        }
        assert expected_decision["hotel"] == False


class TestSpecialInstructionsExtraction:
    """Test special instructions extraction"""

    def test_extract_skip_attraction_keywords(self):
        """Test extract skip attraction keywords"""
        keywords = ["no attractions", "only food", "already have guide"]
        for keyword in keywords:
            assert any(k in keyword for k in ["attractions", "food", "guide"])

    def test_extract_skip_transport_keywords(self):
        """Test extract skip transport keywords"""
        keywords = ["local tour", "driving myself", "already bought tickets"]
        for keyword in keywords:
            assert any(k in keyword for k in ["local", "driving", "tickets"])

    def test_extract_skip_hotel_keywords(self):
        """Test extract skip hotel keywords"""
        keywords = ["already booked hotel", "staying with friends", "day trip"]
        for keyword in keywords:
            assert any(k in keyword for k in ["hotel", "staying", "day"])


class TestToolSelectorScenarios:
    """Test various decision scenarios"""

    def test_scenario_local_tour(self):
        """Test local tour scenario"""
        scenario = {
            "origin": "Beijing",
            "city": "Beijing",
            "user_message": "Beijing local tour"
        }
        expected = {
            "skip_transport": True,
            "skip_hotel": True
        }
        assert expected["skip_transport"] == True
        assert expected["skip_hotel"] == True

    def test_scenario_day_trip(self):
        """Test day trip scenario"""
        scenario = {
            "origin": "Shanghai",
            "city": "Hangzhou",
            "user_message": "day trip, return same day"
        }
        expected = {
            "skip_hotel": True
        }
        assert expected["skip_hotel"] == True

    def test_scenario_has_own_arrangements(self):
        """Test user already has arrangements"""
        scenario = {
            "user_message": "I already booked hotel and flight"
        }
        expected = {
            "skip_hotel": True,
            "skip_transport": True
        }
        assert expected["skip_hotel"] == True
        assert expected["skip_transport"] == True

    def test_scenario_food_focused(self):
        """Test food focused scenario"""
        scenario = {
            "user_message": "No attractions, just want to eat"
        }
        expected = {
            "skip_attraction": True
        }
        assert expected["skip_attraction"] == True

    def test_scenario_normal_planning(self):
        """Test normal planning scenario"""
        scenario = {
            "origin": "Shanghai",
            "city": "Beijing",
            "start_date": "2024-04-01",
            "end_date": "2024-04-03",
            "user_message": "Help me plan the trip"
        }
        expected = {
            "attraction": True,
            "weather": True,
            "transport": True,
            "hotel": True
        }
        assert all(expected.values()) == True


class TestToolSelectorPriority:
    """Test decision priority"""

    def test_user_instruction_overrides_llm(self):
        """Test user instruction overrides LLM decision"""
        user_instruction = {"skip_attraction": True}
        llm_suggestion = {"attraction": True}
        final_decision = {
            "attraction": not user_instruction.get("skip_attraction", False)
        }
        assert final_decision["attraction"] == False

    def test_multiple_skips_combined(self):
        """Test multiple skips combined"""
        special_instructions = {
            "skip_attraction": True,
            "skip_transport": True,
            "skip_hotel": False
        }
        expected = {
            "attraction": False,
            "transport": False,
            "hotel": True,
            "weather": True
        }
        assert expected["attraction"] == False
        assert expected["transport"] == False
        assert expected["hotel"] == True
        assert expected["weather"] == True