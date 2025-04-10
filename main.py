#!/usr/bin/env python3
import sys, argparse
from yaspin import yaspin
from datetime import datetime
from search import get_search_results
from scrape import scrape_multiple
from llm import get_llm, refine_query, generate_summary, filter_results

import warnings
warnings.filterwarnings("ignore")

def main():
    parser = argparse.ArgumentParser(
        description="Robin: AI-Powered Dark Web OSINT Tool",
        epilog=(
            "Example commands:\n"
            " - robin -m gpt4o -q \"ransomware payments\" -t 12 \n"
            " - robin --model claude-3-5-sonnet-latest --query \"sensitive credentials exposure\" --threads 8 --output filename\n"
            " - robin -m llama3.1 -q \"zero days\" \n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--model", '-m', 
        type=str, 
        choices=["gpt4o", "claude-3-5-sonnet-latest", "llama3.1"],
        default="gpt4o",
        help="Select LLM model (e.g., gpt4o, claude sonnet 3.5, ollama models)"
    )
    parser.add_argument(
        "--query", '-q', 
        type=str, 
        required=True, 
        help="Dark web search query"
    )
    parser.add_argument(
        "--threads", '-t',
        type=int, 
        default=5, 
        help="Number of threads to use for scraping (Default: 5)"
    )
    parser.add_argument(
        "--output", '-o',
        type=str,
        help="Filename to save the final intelligence summary. If not provided, a filename based on the current date and time is used."
    )
    
    # Check if no additional args are provided; if so, show help and exit.
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()

    llm = get_llm(args.model)
    user_input = args.query

    # Show spinner while processing the query
    with yaspin(text="Processing...", color="cyan") as sp:
        refined_query = refine_query(llm, user_input)
        
        search_results = get_search_results(refined_query.replace(' ', '+'), max_workers=args.threads)

        search_filtered = filter_results(llm, refined_query, search_results)

        scraped_results = scrape_multiple(
            search_filtered,
            max_workers=args.threads
        )
        sp.ok("✔")
    
    # Generate the intelligence summary.
    summary = generate_summary(llm, user_input, scraped_results)
    
    # Save the final intelligence summary to a file.
    if not args.output:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"summary_{now}.md"
    else:
        filename = args.output + ".md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(summary)
    
    print(f"\n\n[Output] Final intelligence summary saved to: {filename}")

if __name__ == '__main__':
    main()
