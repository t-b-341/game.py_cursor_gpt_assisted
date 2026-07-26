"""Display profiling results from existing files."""
import os
import pstats

from profile_game import detect_startup_mechanism, summarize_slowest_functions
from io import StringIO






def main():
    if not os.path.exists("profiling_results.prof"):
        print("Error: profiling_results.prof not found")
        return 1
    
    if not os.path.exists("profiling_results.txt"):
        print("Error: profiling_results.txt not found")
        return 1
    
    # Read the text file
    with open("profiling_results.txt", "r", encoding="utf-8") as f:
        stats_lines = f.read().splitlines()
    
    # Output results
    print("\n" + "="*80)
    print("PROFILING RESULTS - First 60 lines:")
    print("="*80)
    for i, line in enumerate(stats_lines[:60], 1):
        print(line)
    
    print("\n" + "="*80)
    print("DETECTED STARTUP MECHANISM:")
    print("="*80)
    print(detect_startup_mechanism())
    
    print("\n" + "="*80)
    print("TOP ~10 SLOWEST FUNCTIONS (by cumulative time):")
    print("="*80)
    slowest = summarize_slowest_functions(stats_lines)
    if slowest:
        for cumtime, func_name, full_line in slowest:
            print(f"  {cumtime:.4f}s - {func_name}")
            print(f"    {full_line[:100]}...")
    else:
        print("  (No function data available)")
    
    print("\n[Profiler] Display complete!")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
