from abc import ABC, abstractmethod
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Input, Static, ListView, ListItem, Label
from textual.binding import Binding
from textual.message import Message
from textual import events
from typing import List, Optional, Tuple
import re


class AutocompleteProvider(ABC):
    """Abstract base class for autocomplete providers."""
    
    @abstractmethod
    def get_mention_prefix(self) -> List[str]:
        """Return the list of prefix for mentions."""
        pass

    @abstractmethod
    def get_suggestions(self, query: str) -> List[str]:
        """Return a list of suggestions for the given query."""
        pass



class AutocompleteInput(Input):
    """Custom Input widget with autocomplete functionality."""
    
    class AutocompleteSelected(Message):
        """Message sent when an autocomplete suggestion is selected."""
        def __init__(self, suggestion: str) -> None:
            self.suggestion = suggestion
            super().__init__()
    
    def __init__(self, provider: AutocompleteProvider, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider = provider
        self.autocomplete_active = False
        self.current_mention_start = -1
        self.current_query = ""
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes to detect @ mentions."""
        cursor_pos = self.cursor_position
        text = self.value
        
        # Find the last prefix before the cursor
        mention_start = -1
        for i in range(cursor_pos - 1, -1, -1):
            if text[i] in self.provider.get_mention_prefix():
                mention_start = i
                break
            elif text[i].isspace():
                break
        
        if mention_start != -1:
            # Extract the query after the prefix
            query_end = cursor_pos
            for i in range(mention_start + 1, len(text)):
                if text[i].isspace():
                    query_end = i
                    break
            
            query = text[mention_start:query_end]
            
            # Only show autocomplete if cursor is within the mention
            if mention_start <= cursor_pos <= query_end:
                self.current_mention_start = mention_start
                self.current_query = query
                self.autocomplete_active = True
                self.post_message(self.AutocompleteSelected(f"SHOW:{query}"))
            else:
                self._hide_autocomplete()
        else:
            self._hide_autocomplete()
    
    def _hide_autocomplete(self):
        """Hide the autocomplete popup."""
        if self.autocomplete_active:
            self.autocomplete_active = False
            self.post_message(self.AutocompleteSelected("HIDE"))
    
    def insert_suggestion(self, suggestion: str) -> None:
        """Insert the selected suggestion into the input."""
        if not self.autocomplete_active:
            return
        
        text = self.value
        # Replace the entire mention span (including prefix) with the suggestion
        start = self.current_mention_start
        end = start + len(self.current_query)
        new_text = text[:start] + suggestion + text[end:]
        self.value = new_text
        # Position cursor after the inserted suggestion
        self.cursor_position = start + len(suggestion)
        
        self._hide_autocomplete()

    def preview_suggestion(self, suggestion: str) -> None:
        """Preview the suggestion by replacing only the current mention span.

        Does not close autocomplete; meant for up/down navigation preview.
        """
        if not self.autocomplete_active:
            return
        text = self.value
        start = self.current_mention_start
        end = start + len(self.current_query)
        new_text = text[:start] + suggestion + text[end:]
        self.value = new_text
        self.cursor_position = start + len(suggestion)


class AutocompletePopup(Container):
    """Popup container for autocomplete suggestions."""
    
    def __init__(self, provider: AutocompleteProvider):
        super().__init__()
        self.provider = provider
        self.suggestions_list = ListView()
        self.visible = False
    
    def compose(self) -> ComposeResult:
        with Container(id="autocomplete-container"):
            yield Static("Suggestions:", classes="popup-title")
            yield self.suggestions_list
    
    def show_suggestions(self, query: str) -> None:
        """Show autocomplete suggestions for the given query."""
        suggestions = self.provider.get_suggestions(query)
        
        # Clear and populate the list
        self.suggestions_list.clear()
        for suggestion in suggestions:
            self.suggestions_list.append(ListItem(Label(f"{suggestion}")))
        
        self.visible = True
        self.add_class("visible")
    
    def hide(self) -> None:
        """Hide the autocomplete popup."""
        self.visible = False
        self.remove_class("visible")
        self.suggestions_list.clear()
    
    def get_selected_suggestion(self) -> Optional[str]:
        """Get the currently selected suggestion."""
        if self.suggestions_list.highlighted_child:
            label = self.suggestions_list.highlighted_child.query_one(Label)
            value = label.renderable
            # Value can be a plain string or a Rich Text object; normalize to str
            if isinstance(value, str):
                return value
            # Try .plain if available (e.g., rich.text.Text)
            plain = getattr(value, "plain", None)
            if plain is not None:
                return plain
            # Fallback to string conversion
            return str(value)
        return None
