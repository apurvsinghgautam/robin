import json
import logging
import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm import get_llm
from search import get_search_results
from scrape import scrape_multiple
from yaspin import yaspin

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SwarmAgent:
    def __init__(self, role, model_name):
        self.role = role
        self.model_name = model_name
        self.llm = get_llm(model_name)

    def run(self, task_description, input_data):
        prompt = ChatPromptTemplate.from_template(
            "Role: {role}\n Task: {task}\n Input: {input}"
        )
        chain = prompt | self.llm | StrOutputParser()
        return chain.invoke({"role": self.role, "task": task_description, "input": input_data})

class ForensicSubSystem:
    """
    The 'Sub-System' comprised of Gemini (Eyes) and Mistral (Brain).
    """
    def __init__(self):
        self.analyst = SwarmAgent(role="Forensic Analyst", model_name="gemini-2.5-flash")
        self.profiler = SwarmAgent(role="Criminal Profiler", model_name="mistral-large")

    def deep_analysis(self, scraped_data):
        """
        1. Gemini extracts raw facts/PII.
        2. Mistral interprets significance and suggests next moves.
        """
        # --- 1. Gemini Extraction ---
        full_content = "\n\n".join([f"Source: {url}\nContent: {content[:15000]}" for url, content in scraped_data.items()])
        
        extraction_task = """
        Analyze the scraped text for PII (Personally Identifiable Information) and Credential Leaks.
        Extract specific artifacts:
        - Emails, Passwords, Hashes
        - Names, Addresses, Phone Numbers
        - SSNs, IDs
        - Crypto Wallets
        
        Return a structured Markdown list of findings. If none, state "No significant PII found."
        """
        pii_report = self.analyst.run(extraction_task, full_content)

        # --- 2. Mistral Synthesis & Pivot ---
        synthesis_task = """
        Review the PII Analysis and the raw data context.
        1. Assess the severity of the findings.
        2. Identify GAPS in the intelligence. What is missing?
        3. Suggest a specific 'Next Search Query' to fill those gaps.
        
        Output Format:
        SEVERITY: [High/Medium/Low]
        INSIGHT: [Summary]
        SUGGESTED_QUERY: [Specific search query string]
        """
        intelligence_brief = self.profiler.run(synthesis_task, pii_report)
        
        return {
            "intelligence_brief": intelligence_brief
        }

class CriticAgent(SwarmAgent):
    def __init__(self):
        super().__init__(role="Verification Auditor", model_name="groq-llama3-70b")

    def review_report(self, draft_report, history_context):
        review_task = """
        You are the Internal Auditor for a high-stakes investigation. 
        Review the drafted Intelligence Report for hallucinations, weak evidence, or logical jumps.
        
        Rules:
        1. If a claim is made (e.g., "Target owns wallet X"), verify if the raw history supports it.
        2. Assign a Confidence Score (0-100%) to the profile.
        3. If confident, return the report endorsed.
        4. If issues found, add a "WARNING SECTION" at the top detailing the unproven claims.
        
        Return the Final Report (modified if necessary).
        """
        input_data = f"DRAFT REPORT:\n{draft_report}\n\nEVIDENCE HISTORY:\n{history_context}"
        return self.run(review_task, input_data)

class GroqOrchestrator:
    """
    The 'Main Orchestrator' (System 1) that runs the control loop.
    """
    def __init__(self, user_query):
        self.user_query = user_query
        self.global_state = {
            "original_query": user_query,
            "history": [],
            "artifacts": [],
            "status": "INITIALIZING"
        }
        self.groq_brain = SwarmAgent(role="Investigation Commander", model_name="groq-llama3-70b")
        self.forensic_team = ForensicSubSystem()

    def decide_next_step(self):
        """
        Groq decides the next action based on Global State.
        """
        decision_task = """
        You are the Commander of a Dark Web Investigation.
        Review the Current State and decide the next immediate action.

        ACTIONS AVAILABLE:
        - SEARCH: Run a single dark web search.
        - PARALLEL_SEARCH: Run multiple distinct searches simultaneously (Use when disjoint leads found, e.g., Crypto vs Email).
        - FINISH: Investigation is complete.

        RULES:
        1. If starting, use PARALLEL_SEARCH to cover broad keywords (e.g., ["{query} password", "{query} dox"]).
        2. If PII found, pivot.
        3. Max 3 cycles.
        
        Return ONLY a JSON object:
        {{
            "action": "SEARCH" | "PARALLEL_SEARCH" | "FINISH",
            "queries": ["query1", "query2"] (List of strings, required for SEARCH/PARALLEL_SEARCH),
            "reason": "Short explanation"
        }}
        """
        state_summary = json.dumps({
            "query": self.global_state["original_query"],
            "history_count": len(self.global_state["history"]),
            "last_step_output": self.global_state["history"][-1] if self.global_state["history"] else "None"
        }, default=str)

        try:
            response = self.groq_brain.run(decision_task, state_summary)
            # Clean JSON Code blocks if present
            clean_json = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)
        except Exception as e:
            logger.error(f"Groq Decision Failed: {e}")
            return {"action": "FINISH", "reason": "Error in decision logic"}

    def execute_search_cycle(self, query, threads):
        """
        Executes: Search -> Filter (Groq) -> Scrape -> Analyze (Sub-System)
        """
        step_data = {"type": "search_cycle", "query": query, "timestamp": datetime.datetime.now().isoformat()}
        
        # 1. Search
        with yaspin(text=f"[Groq] Ordering Search: {query}", color="cyan") as sp:
            raw_results = get_search_results(query.replace(" ", "+"), max_workers=threads)
            
            # 2. Filter (Groq Fast Filter)
            filter_task = "Select top 10 indices of results most likely to contain PII/Leaks. Return JSON list: [1, 3...]"
            results_str = "\n".join([f"{i}. {r['link']} - {r['title']}" for i, r in enumerate(raw_results)])
            filter_resp = self.groq_brain.run(filter_task, results_str)
            try:
                indices = [int(x) for x in re.findall(r'\d+', filter_resp)][:10]
                targets = [raw_results[i] for i in indices if i < len(raw_results)]
            except:
                targets = raw_results[:5]
            
            sp.write(f"> Targeting {len(targets)} URLs.")
            sp.ok("✔")

        # 3. Scrape
        with yaspin(text="[System] Acquiring Data...", color="yellow") as sp:
            scraped = scrape_multiple(targets, max_workers=threads)
            sp.ok("✔")

        # 4. Deep Analysis (Sub-System)
        with yaspin(text="[Forensics] Gemini & Mistral Analyzing...", color="magenta") as sp:
            analysis_result = self.forensic_team.deep_analysis(scraped)
            step_data["analysis"] = analysis_result
            step_data["raw_content_sample"] = str(list(scraped.values())[0])[:500] if scraped else "No Data"
            sp.ok("✔")
            
        self.global_state["history"].append(step_data)
        return analysis_result



    def run_loop(self, threads):
        print(f"\n[Commander] Starting Investigation on: {self.user_query}")
        
        loop_active = True
        step_count = 0
        
        while loop_active and step_count < 3: # Safety brake
            decision = self.decide_next_step()
            action = decision.get("action")
            queries = decision.get("queries", [])
            # Fallback for old single query format
            if "query" in decision and not queries:
                queries = [decision["query"]]
            
            print(f"\n[Command] Action: {action} | Refs: {queries}")

            if action in ["SEARCH", "PARALLEL_SEARCH"]:
                if not queries:
                     queries = [self.user_query]
                
                # Execute Parallel Swarms
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {executor.submit(self.execute_search_cycle, q, threads): q for q in queries}
                    for future in as_completed(futures):
                        q = futures[future]
                        try:
                            res = future.result()
                            print(f"[Swarm-Thread] Finished cycle for: {q}")
                        except Exception as e:
                            logger.error(f"[Swarm-Thread] Error on {q}: {e}")
                
                step_count += 1
            elif action == "FINISH":
                loop_active = False
            else:
                loop_active = False
        
        return self.global_state

def run_swarm_investigation(user_query, threads=5, output_prefix=None):
    # Initialize Orchestrator
    orchestrator = GroqOrchestrator(user_query)
    
    # Run Control Loop
    final_state = orchestrator.run_loop(threads)
    
    # Generate Final Output
    if not output_prefix:
        output_prefix = f"investigation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Save Raw Data
    with open(f"{output_prefix}_raw_data.json", "w", encoding="utf-8") as f:
        json.dump(final_state, f, indent=2, default=str)

    # Save Executive Report
    # Using Mistral one last time to summarize the entire history
    profiler = SwarmAgent(role="Chief of Intelligence", model_name="mistral-large")
    
    final_task = """
    Review the entire investigation history (multiple search cycles).
    Compile a Final Executive Report:
    1. Consolidated PII Findings (Merge from all cycles)
    2. Threat Profile
    3. Final Recommendations
    """
    history_str = json.dumps(final_state["history"], default=str)
    final_report_draft = profiler.run(final_task, history_str) # Mistral Context window is large enough mostly.
    
    # 3. Critic Review
    critic = CriticAgent()
    with yaspin(text="[Critic] Auditing Report...", color="red") as sp:
        final_report_approved = critic.review_report(final_report_draft, history_str[:30000]) # Truncate if massive
        sp.ok("✔")

    with open(f"{output_prefix}_report.md", "w", encoding="utf-8") as f:
        f.write(f"# Final Investigation Report\n\n{final_report_approved}")

    print(f"\n[SUCCESS] Investigation Completed.")
    print(f" > Report: {output_prefix}_report.md")
