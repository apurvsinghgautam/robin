"""Report service for generating and exporting reports."""
from datetime import datetime
from typing import Optional
from uuid import UUID
import io


class ReportService:
    """
    Generates and exports investigation reports.

    Supports multiple export formats: Markdown, HTML, PDF.
    """

    def generate_from_investigation(
        self,
        investigation_id: UUID,
        title: str,
        query: str,
        response: str,
        tools_used: list[dict],
        subagent_results: list[dict],
    ) -> dict:
        """
        Generate a structured report from investigation results.

        Returns:
            Report structure with sections
        """
        sections = []

        # Executive Summary section
        sections.append({
            "id": "summary",
            "type": "summary",
            "title": "Executive Summary",
            "content": self._generate_summary(query, response),
        })

        # Investigation Query section
        sections.append({
            "id": "query",
            "type": "text",
            "title": "Investigation Query",
            "content": query,
        })

        # Tools Used section
        if tools_used:
            sections.append({
                "id": "tools",
                "type": "tools",
                "title": "Investigation Tools Used",
                "content": self._format_tools(tools_used),
            })

        # Sub-agent Analysis sections
        for i, sa_result in enumerate(subagent_results):
            if sa_result.get("success"):
                sections.append({
                    "id": f"subagent_{i}",
                    "type": "analysis",
                    "title": f"{sa_result['agent_type']} Analysis",
                    "content": sa_result.get("analysis", ""),
                })

        # Full Response section
        sections.append({
            "id": "response",
            "type": "text",
            "title": "Full Investigation Response",
            "content": response,
        })

        return {
            "title": title,
            "summary": self._generate_summary(query, response)[:500],
            "sections": sections,
            "metadata": {
                "investigation_id": str(investigation_id),
                "generated_at": datetime.now().isoformat(),
                "tools_count": len(tools_used),
                "subagents_used": [
                    r["agent_type"]
                    for r in subagent_results
                    if r.get("success")
                ],
            },
        }

    def _generate_summary(self, query: str, response: str) -> str:
        """Generate a brief summary of the investigation."""
        # Take first paragraph or first 500 chars as summary
        paragraphs = response.split("\n\n")
        if paragraphs:
            summary = paragraphs[0][:500]
            if len(paragraphs[0]) > 500:
                summary += "..."
            return summary
        return response[:500]

    def _format_tools(self, tools_used: list[dict]) -> str:
        """Format tools list for display."""
        lines = []
        for i, tool in enumerate(tools_used, 1):
            name = tool.get("name", "unknown")
            # Simplify tool name
            display_name = name.replace("mcp__robin__", "")
            lines.append(f"{i}. **{display_name}**")

            # Add input summary if available
            input_data = tool.get("input", {})
            if "query" in input_data:
                lines.append(f"   Query: `{input_data['query']}`")
            elif "targets" in input_data:
                targets = input_data["targets"]
                lines.append(f"   Targets: {len(targets)} URLs")

        return "\n".join(lines)

    def export_markdown(self, report: dict) -> str:
        """Export report as Markdown."""
        lines = []

        # Title
        lines.append(f"# {report['title']}")
        lines.append("")
        lines.append(f"*Generated: {report.get('metadata', {}).get('generated_at', 'Unknown')}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Sections
        for section in report.get("sections", []):
            lines.append(f"## {section['title']}")
            lines.append("")
            lines.append(section["content"])
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def export_html(self, report: dict) -> str:
        """Export report as HTML."""
        html_parts = []

        html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
            background: #0a0a0a;
            color: #e5e5e5;
        }}
        h1 {{ color: #fff; border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
        h2 {{ color: #ddd; margin-top: 2rem; }}
        pre {{ background: #1a1a1a; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
        code {{ background: #1a1a1a; padding: 0.2rem 0.4rem; border-radius: 2px; }}
        hr {{ border: none; border-top: 1px solid #333; margin: 2rem 0; }}
        .metadata {{ color: #888; font-size: 0.9rem; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ border: 1px solid #333; padding: 0.5rem; text-align: left; }}
        th {{ background: #1a1a1a; }}
    </style>
</head>
<body>
""".format(title=report['title']))

        html_parts.append(f"<h1>{report['title']}</h1>")
        html_parts.append(f"<p class='metadata'>Generated: {report.get('metadata', {}).get('generated_at', 'Unknown')}</p>")
        html_parts.append("<hr>")

        for section in report.get("sections", []):
            html_parts.append(f"<h2>{section['title']}</h2>")
            # Simple markdown to HTML conversion
            content = section["content"]
            content = content.replace("\n\n", "</p><p>")
            content = f"<p>{content}</p>"
            html_parts.append(content)
            html_parts.append("<hr>")

        html_parts.append("</body></html>")

        return "\n".join(html_parts)

    def export_json(self, report: dict) -> dict:
        """Export report as JSON (passthrough with cleanup)."""
        return {
            "title": report["title"],
            "summary": report.get("summary", ""),
            "sections": report.get("sections", []),
            "metadata": report.get("metadata", {}),
        }
