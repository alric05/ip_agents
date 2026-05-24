#!/usr/bin/env python3
"""Test script for the Novelty Checker - Phase 2: Confirm and Search.

This continues from the scoping phase to test the search functionality.
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
from langchain_core.messages import HumanMessage, AIMessage

# Import the deep agent
from src.novelty_checker.deep_agent import create_deep_agent
from src.config.settings import get_settings

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
- Achieves several times higher (3…5 or more) transmission ratio conversions
- Benefits in power consumption levels  
- Achieves compactness due to novel dual-worm gear arrangement
- Offers two driving possibilities: horizontal rotary drive and direct vertical elevation
- Application for retracting/protruding camera lenses in smartphones
- Silent operation, simpler manufacturing, lower costs
"""


def get_llm():
    """Get configured LLM."""
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.google_api_key,
        temperature=0,
    )


def run_search_test():
    """Run the search phase test."""
    print("\n" + "="*60)
    print("NOVELTY CHECKER - SEARCH PHASE TEST")
    print("="*60)
    
    llm = get_llm()
    agent, session_id = create_deep_agent(model=llm)
    print(f"Session ID: {session_id}")
    config = {"configurable": {"thread_id": "test-search-phase"}}
    
    # Simulate the conversation with confirmation
    initial_state = {
        "messages": [
            HumanMessage(content=f"""Please check the novelty of this invention:

{TEST_IDEA}

Start by scoping the invention and creating a plan."""),
            AIMessage(content="""I have scoped the invention:

**Scope**: Dual-worm gear transmission system for compact smartphone camera lens actuation.

**Features**:
- F1: Dual-Worm Gear System with adapter gear
- F2: High Transmission Ratio (3-5x higher than prior art)
- F3: Compact Form Factor for smartphones
- F4: Retracting/Protruding Lens Actuation
- F5: Dual drive options (horizontal rotary + vertical leadscrew)

Awaiting confirmation before proceeding to search."""),
            HumanMessage(content="""Confirmed. The scope and features look good. 

Please proceed with the patent and NPL searches. Focus on:
1. F1 (dual-worm gear system) - this is the core novelty
2. F2 (high transmission ratio)
3. F4 (smartphone camera lens actuation)

Use the batch_unified_search tool to efficiently search patents, NPL, and semantic in one go."""),
        ],
        "customer_idea": TEST_IDEA,
        "current_stage": "patent_search",
        "scope_confirmed": True,
        "features_confirmed": True,
        "features": [
            {"id": "F1", "name": "Dual-Worm Gear System", "description": "Transmission with two worm gears and adapter gear", "keywords": ["worm gear", "dual worm", "adapter gear", "transmission"], "is_core": True, "priority": "P1"},
            {"id": "F2", "name": "High Transmission Ratio", "description": "3-5x higher ratio than prior art", "keywords": ["transmission ratio", "gear ratio", "torque multiplication"], "is_core": True, "priority": "P1"},
            {"id": "F3", "name": "Compact Form Factor", "description": "Designed for smartphone camera space", "keywords": ["compact", "miniature", "smartphone camera"], "is_core": False, "priority": "P2"},
            {"id": "F4", "name": "Lens Actuation", "description": "Retracting/protruding camera lenses", "keywords": ["lens actuator", "camera lens", "retractable lens"], "is_core": True, "priority": "P1"},
            {"id": "F5", "name": "Dual Drive Options", "description": "Horizontal rotary and vertical leadscrew", "keywords": ["rotary drive", "leadscrew", "linear actuator"], "is_core": False, "priority": "P2"},
        ],
    }
    
    print("\nRunning agent with search confirmation...")
    print("(This will execute actual API calls to Innography/WoS/NGSP)")
    print("-"*60 + "\n")
    
    try:
        result = agent.invoke(
            initial_state, 
            config={
                **config,
                "recursion_limit": 50,  # Allow more steps for complex searches
            }
        )
        
        print("\n" + "="*60)
        print("AGENT SEARCH RESPONSE")
        print("="*60 + "\n")
        
        # Print the last AI message
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "content") and msg.content:
                print(msg.content)
                break
        
        print("\n" + "="*60)
        print("SEARCH TEST COMPLETE")
        print("="*60)
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    run_search_test()
