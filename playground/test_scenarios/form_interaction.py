#!/usr/bin/env python3
"""
Form Interaction Test Scenario

Test form filling and interaction functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add src to Python path  
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


async def test_form_interaction():
    """Test form interaction functions."""
    print("📝 Testing Form Interaction")
    print("=" * 40)
    
    # Test commands for Claude Code
    test_commands = [
        "Navigate to https://httpbin.org/forms/post",
        "Take a screenshot to see the form",
        "Input 'testuser' into the field with name 'custname'", 
        "Input 'user@example.com' into the field with name 'custemail'",
        "Select the 'Large' radio button",
        "Input 'This is a test comment' into the textarea",
        "Click the submit button",
        "Take a screenshot of the result"
    ]
    
    print("📝 Test Commands to use with Claude Code:")
    for i, command in enumerate(test_commands, 1):
        print(f"  {i}. {command}")
    
    print("\n💡 Expected Results:")
    print("  • Form should load with input fields")
    print("  • Text should be input into fields")
    print("  • Radio button should be selected")
    print("  • Form should submit successfully")
    print("  • Result page should show submitted data")
    
    print("\n🎯 Alternative Test Sites:")
    print("  • https://httpbin.org/forms/post (Simple form)")
    print("  • https://the-internet.herokuapp.com/login (Login form)")
    print("  • https://reqres.in/ (API testing)")


if __name__ == "__main__":
    asyncio.run(test_form_interaction())