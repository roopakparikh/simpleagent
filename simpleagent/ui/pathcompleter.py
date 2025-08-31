from __future__ import annotations

import os
import re
from typing import Optional
from simpleagent.ui.autocomplete import AutocompleteProvider
import glob

def _resolve_abs_path(base_dir: str, path_text: str) -> str:
    """Resolve a user-entered path (possibly relative, with ~ or env vars) to an absolute path.

    Relative paths are resolved against the completer's base_dir.
    """
    expanded = os.path.expandvars(os.path.expanduser(path_text))
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    return os.path.abspath(os.path.join(base_dir, expanded))


def get_path_completed_text(base_dir: str, text: str):
    """Replace occurrences of @<path> in text with absolute paths.

    Returns a tuple (new_text, mapping) where mapping is a list of (original, expanded).
    """
    pattern = re.compile(r"@(\S+)")
    mappings = []

    def repl(match):
        orig = match.group(0)  # includes '@'
        path_part = match.group(1)
        abs_path = _resolve_abs_path(base_dir, path_part)
        mappings.append((orig, abs_path))
        return abs_path

    new_text = pattern.sub(repl, text)
    return new_text, mappings


class AtPathSuggester(AutocompleteProvider):
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.prefix = "@"

    def get_mention_prefix(self) -> List[str]:
        return [self.prefix]
    
    def _list_matches(self, path_text: str) -> list[str]:
        # Expand user home (~) and environment vars
        expanded = os.path.expandvars(os.path.expanduser(path_text))
        # Build search pattern
        if expanded == "":
            pattern = os.path.join(self.base_dir, "*")
        elif os.path.isabs(expanded):
            pattern = expanded + "*"
        else:
            pattern = os.path.join(self.base_dir, expanded + "*")

        matches = []
        for match in glob.glob(pattern):
            if not os.path.isabs(expanded) and match.startswith(self.base_dir + os.sep):
                rel = os.path.relpath(match, self.base_dir)
            else:
                rel = match
            if os.path.isdir(match):
                matches.append(rel + "/")
            else:
                matches.append(rel)
        matches.sort()
        return matches

    def get_suggestions(self, query: str) -> List[str]:
        query = query[1:]  # Remove the prefix
        matches = self._list_matches(query)
        final_matches = [self.prefix + item for item in matches]
        return final_matches
        


class DictAutocompleteProvider(AutocompleteProvider):
    
    def __init__(self, prefix: str, data: Set[str]):
        self.data = list(data)
        self.prefix = prefix
    
    def get_suggestions(self, query: str) -> List[str]:
        """Filter data based on the query."""
        if not query:
            return self.data[:10]  # Return first 10 if no query
        query = query[1:]  # Remove the prefix
        query_lower = query.lower()
        matches = [self.prefix + item for item in self.data if query_lower in item.lower()]
        return matches[:15]  # Return up to 15 matches

    def get_mention_prefix(self) -> List[str]:
        return [self.prefix]
        

class CompositeAutocompleteProvider(AutocompleteProvider):
    def __init__(self, providers: List[AutocompleteProvider]):
        self.providers = providers
        prefixes = []
        for provider in self.providers:
            prefixes.extend(provider.get_mention_prefix())
        self.prefixes = prefixes
    
    def get_suggestions(self, query: str) -> List[str]:
        suggestions = []
        # select the provider based on the prefix associated with the provider
        for provider in self.providers:
            if query.startswith(provider.get_mention_prefix()[0]):
                suggestions.extend(provider.get_suggestions(query))
        return suggestions
    
    def get_mention_prefix(self) -> List[str]:
        return self.prefixes