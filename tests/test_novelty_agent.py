#!/usr/bin/env python3
"""Test script for the Novelty Checker deep agent.

This script tests the full pipeline with a sample invention idea.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# Import the deep agent
from src.novelty_checker.deep_agent import create_deep_agent
from src.tools import get_all_tools
from src.config.settings import get_settings, get_config_status

# Test invention idea
TEST_IDEA = """
Conventional digital still cameras can accommodate more thicker lens system as the 
thickness of the product is natively more bulky. However smartphones are natively 
much more thinner devices (10-13 mm), which need the lenses to be arranged more 
efficiently inside the camera space compartment. In order to electromechanically 
arrange the lenses, a suitable mechanism and actuation arrangement is needed for 
the movement generation. 

New solution utilizes the normal worm gear approach but introduces another (second) 
worm gear into the same transmission system. This result the most compact ultra high 
ratio transmission system which can be applied to operate e.g. the retracting lens 
system as two worm gears cannot be directly coupled, an adapter gear #3 is needed 
in between them. 

Summary of the benefits:
- Achieves several times higher (3…5 or more) transmission ratio conversions than 
  prior art systems for rotary based drive systems, multiplying also the output torque level.
- Benefits in power consumption levels as the same electrical power can be used more 
  efficiently to drive the actuation system for moving objects.
- Achieves compactness due to novel dual-worm gear arrangement, thus eliminating 
  plurality of separate spur gears.
- Offers two driving possibilities for movable objects, horizontal rotary drive and 
  direct vertical elevation via leadscrew.
- Application-wise both systems can be harnessed to drive retracting/protruding camera 
  lenses inside smartphone camera environment.
- Silent operation as number of gears are reduced.
- Less number of gears results simpler manufacturing and assembly operations.
- Less complex architecture results lower production costs for the unit.
"""


def get_azure_llm():
    """Get configured Google Gemini LLM."""
    settings = get_settings()
    
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.google_api_key,
        temperature=0,
    )


def print_config_status():
    """Print configuration status."""
    print("\n" + "="*60)
    print("CONFIGURATION STATUS")
    print("="*60)
    
    status = get_config_status()
    for service, info in status.items():
        icon = "✅" if info["configured"] else "❌"
        print(f"  {icon} {info['service']}")
    
    print("="*60 + "\n")


def print_tools():
    """Print available tools."""
    print("\n" + "="*60)
    print("AVAILABLE TOOLS")
    print("="*60)
    
    for tool in get_all_tools():
        print(f"  • {tool.name}")
    
    print("="*60 + "\n")


def run_test():
    """Run the novelty check test."""
    print("\n" + "="*60)
    print("NOVELTY CHECKER TEST")
    print("="*60)
    
    # Print config and tools
    print_config_status()
    print_tools()
    
    # Get LLM
    print("Initializing Azure OpenAI LLM...")
    llm = get_azure_llm()
    
    # Test LLM connection
    print("Testing LLM connection...")
    try:
        response = llm.invoke([HumanMessage(content="Say 'OK' if you can hear me.")])
        print(f"  LLM Response: {response.content[:50]}...")
    except Exception as e:
        print(f"  ❌ LLM Error: {e}")
        return
    
    print("\n" + "-"*60)
    print("INVENTION IDEA (first 200 chars):")
    print("-"*60)
    print(TEST_IDEA[:200] + "...")
    print("-"*60 + "\n")
    
    # Create the agent
    print("Creating deep agent...")
    agent, session_id = create_deep_agent(model=llm)
    print(f"Session ID: {session_id}")
    
    # Prepare initial state
    initial_state = {
        "messages": [
            HumanMessage(content=f"""Please check the novelty of this invention:

{TEST_IDEA}

Start by:
1. Scoping the invention (identify the core technical problem and solution)
2. Defining 3-5 key features (F1, F2, etc.)
3. Present the scope and features for confirmation

Do NOT proceed to searching until I confirm the scope and features.""")
        ],
        "customer_idea": TEST_IDEA,
        "current_stage": "scoping",
    }
    
    config = {"configurable": {"thread_id": "test-dual-worm-gear"}}
    
    print("Running agent (this may take a minute)...")
    print("="*60 + "\n")
    
    try:
        result = agent.invoke(initial_state, config=config)
        
        print("\n" + "="*60)
        print("AGENT RESPONSE")
        print("="*60)
        
        # Print the last AI message
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "content") and msg.content:
                print(msg.content)
                break
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
        
        return result
        
    except Exception as e:
        print(f"\n❌ Agent Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    run_test()
