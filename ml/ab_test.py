"""A/B Testing for DDA effectiveness.

This module helps you compare gameplay with DDA enabled vs disabled
to scientifically verify if the ML is improving the experience.

Usage:
    # Run the A/B test protocol
    python -m ml.ab_test
    
    # Analyze results after playing
    python -m ml.ab_test --analyze
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from datetime import datetime

AB_TEST_FILE = Path("dda_ab_test.json")


def get_test_state() -> dict:
    """Load current A/B test state."""
    if AB_TEST_FILE.exists():
        return json.loads(AB_TEST_FILE.read_text())
    return {
        "started": None,
        "sessions": [],
        "current_condition": None,
        "total_dda_on": 0,
        "total_dda_off": 0,
    }


def save_test_state(state: dict):
    """Save A/B test state."""
    AB_TEST_FILE.write_text(json.dumps(state, indent=2))


def start_ab_test():
    """Start a new A/B testing session."""
    state = get_test_state()
    
    if state["started"] is None:
        state["started"] = datetime.now().isoformat()
        print("\n🧪 A/B TEST PROTOCOL STARTED")
        print("=" * 50)
    
    # Randomly assign condition for this session
    if state["total_dda_on"] <= state["total_dda_off"]:
        condition = "DDA_ON"
    else:
        condition = "DDA_OFF"
    
    # Add some randomness
    if random.random() < 0.3:
        condition = "DDA_OFF" if condition == "DDA_ON" else "DDA_ON"
    
    state["current_condition"] = condition
    state["sessions"].append({
        "timestamp": datetime.now().isoformat(),
        "condition": condition,
        "completed": False,
    })
    
    if condition == "DDA_ON":
        state["total_dda_on"] += 1
    else:
        state["total_dda_off"] += 1
    
    save_test_state(state)
    
    print(f"\n🎲 THIS SESSION: {condition}")
    print()
    
    if condition == "DDA_ON":
        print("✅ DDA is ENABLED for this session")
        print("   Difficulty will adjust based on your performance")
        _enable_dda()
    else:
        print("❌ DDA is DISABLED for this session")
        print("   Difficulty uses standard progression")
        _disable_dda()
    
    print()
    print(f"Sessions so far: {state['total_dda_on']} with DDA, {state['total_dda_off']} without")
    print()
    print("Play normally! Your data will be logged for comparison.")
    print("Run 'python -m ml.ab_test --analyze' after several sessions.")


def _enable_dda():
    """Enable DDA for this session."""
    try:
        from ml.dda_integration import get_dda
        dda = get_dda()
        dda.enable()
        print("   [DDA enabled successfully]")
    except Exception as e:
        print(f"   [Warning: Could not enable DDA: {e}]")


def _disable_dda():
    """Disable DDA for this session."""
    try:
        from ml.dda_integration import get_dda
        dda = get_dda()
        dda.disable()
        print("   [DDA disabled successfully]")
    except Exception as e:
        print(f"   [Warning: Could not disable DDA: {e}]")


def analyze_ab_results():
    """Analyze A/B test results."""
    state = get_test_state()
    
    if not state["sessions"]:
        print("\n⚠️  No A/B test sessions found!")
        print("Run 'python -m ml.ab_test' to start testing.")
        return
    
    print("\n" + "=" * 60)
    print("     A/B TEST ANALYSIS")
    print("=" * 60)
    
    print(f"\nTest started: {state.get('started', 'Unknown')}")
    print(f"Total sessions: {len(state['sessions'])}")
    print(f"  - DDA ON:  {state['total_dda_on']}")
    print(f"  - DDA OFF: {state['total_dda_off']}")
    
    # Need telemetry data to do proper analysis
    try:
        from ml.evaluate import (
            get_db_connection,
            get_outcome_distribution,
            get_survival_metrics,
            calculate_dda_effectiveness,
        )
        
        conn = get_db_connection()
        if conn is None:
            print("\n⚠️  No telemetry database found for analysis.")
            return
        
        # Get overall metrics
        effectiveness = calculate_dda_effectiveness(conn)
        survival = get_survival_metrics(conn)
        
        print(f"\n📊 OVERALL METRICS")
        print(f"   DDA Effectiveness Score: {effectiveness['score']:.1f}/100")
        print(f"   Avg waves survived: {survival['avg_waves_survived']:.1f}")
        print(f"   Avg HP at wave end: {survival['avg_hp_at_wave_end']:.1f}%")
        print(f"   Death rate: {survival['death_rate_pct']:.1f}%")
        
        conn.close()
        
    except ImportError:
        print("\n⚠️  Could not import analysis tools.")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    if len(state["sessions"]) < 10:
        print(f"   • Need more data: play {10 - len(state['sessions'])} more sessions")
    elif state["total_dda_on"] < 5 or state["total_dda_off"] < 5:
        print("   • Need more balanced data between conditions")
    else:
        print("   • Enough data for preliminary analysis!")
        print("   • Run 'python -m ml.evaluate' for detailed metrics")


def main():
    parser = argparse.ArgumentParser(description="A/B test DDA effectiveness")
    parser.add_argument("--analyze", action="store_true", help="Analyze test results")
    parser.add_argument("--reset", action="store_true", help="Reset A/B test data")
    
    args = parser.parse_args()
    
    if args.reset:
        if AB_TEST_FILE.exists():
            AB_TEST_FILE.unlink()
        print("A/B test data reset.")
        return
    
    if args.analyze:
        analyze_ab_results()
    else:
        start_ab_test()


if __name__ == "__main__":
    main()
