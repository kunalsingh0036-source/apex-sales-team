"""
Template engine for variable substitution in outreach messages.
"""

import re
from typing import Optional


def render_template(template: str, variables: dict) -> str:
    """Replace {{variable}} placeholders with actual values.

    Args:
        template: Message template with {{variable_name}} placeholders.
        variables: Dict of variable_name -> value mappings.

    Returns:
        Rendered message with placeholders replaced.
    """
    def replacer(match: re.Match) -> str:
        var_name = match.group(1).strip()
        return str(variables.get(var_name, match.group(0)))

    return re.sub(r"\{\{(.+?)\}\}", replacer, template)


def extract_variables(template: str) -> list[str]:
    """Extract all variable names from a template."""
    return [m.strip() for m in re.findall(r"\{\{(.+?)\}\}", template)]
