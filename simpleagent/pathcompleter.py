from __future__ import annotations

import glob
import os
import re
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

class CompositeCompleter(Completer):
    def __init__(self, completers: Dict[str, Completer]):
        self.completers = completers
    
    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        # Find last token boundary (space-separated for simplicity)
        last_space = text.rfind(" ")
        token_start = last_space + 1
        token = text[token_start:]
        for k, v in self.completers.items():
            if token.startswith(k):
                for c in v.get_completions(document, complete_event):
                    yield c
        return
        
class SystemCompleter(Completer):
    def get_completions(self, document: Document, complete_event):
        yield Completion("/exit")
        yield Completion("/quit")
        yield Completion("/help")   

class AtPathCompleter(Completer):
    """prompt_toolkit completer that completes filesystem paths when the
    token being completed starts with '@'. The inserted text keeps the '@' prefix.
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir 

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

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        # Find last token boundary (space-separated for simplicity)
        last_space = text.rfind(" ")
        token_start = last_space + 1
        token = text[token_start:]
        if not token.startswith("@"):
            return
        path_text = token[1:]

        for match in self._list_matches(path_text):
            # Insert with '@' prefix, replace the whole token
            display = match
            insert_text = "@" + match
            yield Completion(
                insert_text,
                start_position=-(len(token)),
                display=display,
            )

    def _resolve_abs_path(self, path_text: str) -> str:
        """Resolve a user-entered path (possibly relative, with ~ or env vars) to an absolute path.

        Relative paths are resolved against the completer's base_dir.
        """
        expanded = os.path.expandvars(os.path.expanduser(path_text))
        if os.path.isabs(expanded):
            return os.path.abspath(expanded)
        return os.path.abspath(os.path.join(self.base_dir, expanded))

    def get_path_completed_text(self, text: str):
        """Replace occurrences of @<path> in text with absolute paths.

        Returns a tuple (new_text, mapping) where mapping is a list of (original, expanded).
        """
        pattern = re.compile(r"@(\S+)")
        mappings = []

        def repl(match):
            orig = match.group(0)  # includes '@'
            path_part = match.group(1)
            abs_path = self._resolve_abs_path(path_part)
            mappings.append((orig, abs_path))
            return abs_path

        new_text = pattern.sub(repl, text)
        return new_text, mappings


def get_prompt_session(root: Optional[str] = None) -> PromptSession:
    """Create a PromptSession with our '@' path completer.

    If 'root' is provided, it will be used as the base directory for
    path completion; otherwise the current working directory is used.
    """
    path_completer = AtPathCompleter(base_dir=root)
    system_completer = SystemCompleter()
    completer = CompositeCompleter({
        "@": path_completer,
        "/": system_completer,
    })
    return PromptSession(completer=completer)

