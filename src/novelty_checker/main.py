#!/usr/bin/env python3
"""Main entry point for the Novelty Checker deep agent.

This module provides a command-line interface for running the novelty
checker interactively or for single idea checks.

Usage:
    python -m novelty_checker.main
    python -m novelty_checker.main "Your invention description"
    python -m novelty_checker.main --interactive
"""

import argparse
import sys
from pathlib import Path
from uuid import uuid4

# Handle optional rich import gracefully
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Novelty Checker - Prior Art Search Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive mode
    python -m novelty_checker.main --interactive
    
    # Single idea check
    python -m novelty_checker.main "A hydraulic valve with variable orifice"
        """,
    )
    
    parser.add_argument(
        "idea",
        type=str,
        nargs="?",
        default=None,
        help="The invention idea to check for novelty",
    )
    
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode for multi-turn conversation",
    )

    parser.add_argument(
        "--thread-id",
        type=str,
        default=None,
        help="Thread ID for conversation persistence (default: random UUID)",
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Use plain text output instead of rich formatting",
    )
    
    return parser


def print_message(msg, verbose: bool = False, use_rich: bool = True):
    """Print a message in a formatted way."""
    from langchain_core.messages import AIMessage, HumanMessage
    
    content = getattr(msg, "content", str(msg))
    
    if use_rich and RICH_AVAILABLE:
        console = Console()
        if isinstance(msg, HumanMessage):
            console.print(f"\n[bold cyan]👤 Human:[/bold cyan] {content}")
        elif isinstance(msg, AIMessage):
            console.print(Panel(Markdown(content), title="🤖 Assistant", border_style="green"))
            if verbose and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    console.print(f"   [dim]🔧 Tool: {tc['name']}[/dim]")
        else:
            console.print(f"\n[dim]📝 {type(msg).__name__}:[/dim] {content}")
    else:
        if isinstance(msg, HumanMessage):
            print(f"\n👤 Human: {content}")
        elif isinstance(msg, AIMessage):
            print(f"\n🤖 Assistant: {content}")
            if verbose and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"   🔧 Tool: {tc['name']}")
        else:
            print(f"\n📝 {type(msg).__name__}: {content}")


def run_interactive(thread_id: str, verbose: bool, use_rich: bool):
    """Run the agent in interactive mode."""
    from langchain_core.messages import HumanMessage, AIMessage
    from src.config.llm import get_llm, get_active_backend_info
    from src.novelty_checker.deep_agent import create_deep_agent
    from src.tools.clients.derwent_auth import check_derwent_jwt, DerwentAuthError

    # Pre-flight: bail with a clear message instead of a traceback when
    # the JWT is missing or expired.
    try:
        check_derwent_jwt()
    except DerwentAuthError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    llm = get_llm()
    backend_info = get_active_backend_info()
    model_display = backend_info["model"]

    if use_rich and RICH_AVAILABLE:
        console = Console()
        console.print(Panel(
            f"[bold]Model:[/bold] {model_display}\n[bold]Thread:[/bold] {thread_id}",
            title="🔍 Novelty Checker - Interactive Mode",
            border_style="cyan"
        ))
        console.print("[dim]Type 'quit' to exit, 'todos' to see tasks, 'help' for commands[/dim]")
    else:
        print("=" * 60)
        print("Novelty Checker - Interactive Mode")
        print("=" * 60)
        print(f"Model: {model_display}")
        print(f"Thread ID: {thread_id}")
        print("Type 'quit' to exit, 'todos' to see tasks, 'help' for commands")
        print("=" * 60)

    agent, session_id = create_deep_agent(model=llm, use_backend_factory=True)
    
    if verbose:
        print(f"[Session: {session_id}]")
    
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 500}
    
    # Initial state
    state = {
        "messages": [],
        "customer_idea": "",
        "current_stage": "scoping",
        "todos": [],
        "features": [],
        "references": [],
    }
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("quit", "exit"):
                print("\n👋 Goodbye!")
                break
            
            if user_input.lower() == "todos":
                print("\n📋 Current Todos:")
                for t in state.get("todos", []):
                    status_icons = {"pending": "⬜", "in_progress": "🔄", "completed": "✅"}
                    status = status_icons.get(t.get("status"), "⬜")
                    print(f"  {status} {t.get('content', '')}")
                if not state.get("todos"):
                    print("  (No todos yet)")
                continue
            
            if user_input.lower() == "help":
                print("""
Commands:
  quit, exit   - End the session
  todos        - Show current todos
  confirm      - Confirm current stage
  help         - Show this help
                """)
                continue
            
            # Add user message
            state["messages"] = state.get("messages", []) + [HumanMessage(content=user_input)]
            
            # Run the agent
            result = agent.invoke(state, config=config)
            
            # Update state
            state = result
            
            # Print the latest AI messages
            for msg in result.get("messages", [])[-3:]:
                if isinstance(msg, AIMessage) and msg.content:
                    print_message(msg, verbose, use_rich)
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            if verbose:
                import traceback
                traceback.print_exc()


def run_single_check(idea: str, thread_id: str, verbose: bool, use_rich: bool):
    """Run a single novelty check on an idea."""
    from langchain_core.messages import AIMessage
    from src.config.llm import get_llm, get_active_backend_info
    from src.novelty_checker.deep_agent import check_novelty

    llm = get_llm()
    backend_info = get_active_backend_info()
    model_display = backend_info["model"]

    if use_rich and RICH_AVAILABLE:
        console = Console()
        console.print(Panel(
            f"[bold cyan]Idea:[/bold cyan] {idea[:100]}{'...' if len(idea) > 100 else ''}",
            title="🔍 Novelty Checker",
            border_style="cyan"
        ))
        console.print(f"\n[dim]Model: {model_display} | Starting analysis...[/dim]\n")
    else:
        print("=" * 60)
        print("Novelty Checker - Single Check Mode")
        print("=" * 60)
        print(f"Idea: {idea[:100]}{'...' if len(idea) > 100 else ''}")
        print(f"Model: {model_display}")
        print("=" * 60)

    check_result = check_novelty(idea=idea, model=llm, thread_id=thread_id, use_backend_factory=True)
    result = check_result["result"]
    session_id = check_result["session_id"]
    
    if verbose:
        print(f"[Session: {session_id}]")
    
    # Print final AI messages
    for msg in result.get("messages", [])[-5:]:
        if isinstance(msg, AIMessage) and msg.content:
            print_message(msg, verbose, use_rich)
    
    # Print todos summary
    if result.get("todos"):
        print("\n📋 Final Todos:")
        for t in result["todos"]:
            status_icons = {"pending": "⬜", "in_progress": "🔄", "completed": "✅"}
            status = status_icons.get(t.get("status"), "⬜")
            print(f"  {status} {t.get('content', '')}")
    
    return result


def main():
    """Main entry point."""
    # Load environment variables (same as studio.py)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    parser = create_parser()
    args = parser.parse_args()

    # Generate thread ID if not provided
    thread_id = args.thread_id or str(uuid4())
    use_rich = RICH_AVAILABLE and not args.plain

    try:
        if args.interactive:
            run_interactive(thread_id, args.verbose, use_rich)
        elif args.idea:
            run_single_check(args.idea, thread_id, args.verbose, use_rich)
        else:
            # Default to interactive if no idea provided
            print("No idea provided. Starting interactive mode...")
            print("(Use positional arg or --idea 'your idea' for single check)")
            run_interactive(thread_id, args.verbose, use_rich)
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all dependencies are installed:")
        print("  pip install langchain langchain-openai langgraph")
        sys.exit(1)


if __name__ == "__main__":
    main()
