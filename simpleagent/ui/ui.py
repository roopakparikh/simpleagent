from __future__ import annotations
from abc import ABC, abstractmethod

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Input, Footer, Header, Static
from textual.widgets import TextArea  # type: ignore
from textual.binding import Binding
from simpleagent.ui.autocomplete import AutocompleteProvider, AutocompleteInput, AutocompletePopup

class ChatCallback(ABC): 
    @abstractmethod
    def on_input_submitted(self, message: str) -> None:
        pass


class SimpleAgentUI(App):
    """A simple TUI with output at the top and a single input at the bottom."""

    CSS = """
    Screen {
        layout: vertical;
    }

    # Optional chrome
    Header {
        dock: top;
    }
    Footer {
        dock: bottom;
    }

    /* Main content sits between header and footer */
    #main {
        layout: vertical;
        height: 1fr;
    }

    /* Output log expands to fill available space */
    #output {
        height: 1fr;
        border: tall $accent;
        padding: 1 1;
    }

    /* Single-line input fixed height at the bottom of main */
    #query {
        height: 3;
    }
    /* Suggestions bar just above the input */
    #suggestions {
        height: auto;
        color: $text 50%;
        padding: 0 1;
        border-top: tall $accent 10%;
        text-style: italic;
    }
    """

    BINDINGS = [
        Binding("escape", "hide_autocomplete", "Hide Autocomplete"),
        Binding("enter", "select_suggestion", "Select Suggestion"),
        Binding("up", "move_up", "Move Up", show=False),
        Binding("down", "move_down", "Move Down", show=False),
    ]
    
    def __init__(self, name: str , autoCompleteProvider: AutocompleteProvider):
        super().__init__()
        self.title = name
        self.autoCompleteProvider = autoCompleteProvider
        self.popup = AutocompletePopup(self.autoCompleteProvider)
        self._output_text: str = ""        # exists before on_mount
        self.output_widget: TextArea | None = None
        self.status = Static("Ready. Type '/' for command '@' for file name suggestions.", id="status")
        self.autocomplete_input = AutocompleteInput(provider= self.autoCompleteProvider, id="query", placeholder="Type a request and press Enter..")
        try:
            import asyncio
            self.ready_event = asyncio.Event()
        except Exception:
            self.ready_event = None

    def set_chat_callback(self, callback: ChatCallback):
        self.chat_callback = callback

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main"):
            # Read-only text area used as an output pane
            yield TextArea(id="output", read_only=True)
            yield Static(id="user_commands")
            # Single-line input for user queries
            yield self.autocomplete_input
            yield self.popup
            yield self.status
        yield Footer()

    def on_mount(self) -> None:
        # Cache widgets
        self.output_widget = self.query_one("#output", TextArea)
        # Flush any buffered output captured before mount
        if self._output_text:
            self.output_widget.text = self._output_text  # type: ignore[attr-defined]
        # Focus the input when the app starts (if present)
        try:
            self.query_one("#query", Input).focus()
        except Exception:
            pass
        # Mark UI as ready for external log handlers
        if getattr(self, "ready_event", None) is not None:
            self.ready_event.set()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter on the input box: echo to output and clear input."""
        query = event.value.strip()
        if not query:
            return

        if self.chat_callback is not None:
            self.chat_callback.on_input_submitted(query)

        # Clear input for the next entry
        event.input.value = ""
        
    def input_out(self, line: str) -> None:
        self.autocomplete_input.value = line

    def console_clear(self) -> None:
        self._output_text = ""
        # TextArea supports setting text directly
        if self.output_widget is not None:
            self.output_widget.text = self._output_text  # type: ignore[attr-defined]
    
    def console_out(self, line: str) -> None:
        # Append to buffer and update UI safely from any thread
        def _append():
            self._output_text += (line + "\n")
            if self.output_widget is not None:
                self.output_widget.text = self._output_text  # type: ignore[attr-defined]
        # If UI not mounted yet, only buffer and return
        if getattr(self, "ready_event", None) is not None and not self.ready_event.is_set():
            self._output_text += (line + "\n")
            return
        try:
            self.call_from_thread(_append)
        except Exception:
            # Fallback to buffer only
            _append()

    def on_autocomplete_input_autocomplete_selected(self, event: AutocompleteInput.AutocompleteSelected) -> None:
        """Handle autocomplete events from the input."""
        if event.suggestion.startswith("SHOW:"):
            query = event.suggestion[5:]  # Remove "SHOW:" prefix
            self.popup.show_suggestions(query)
            self.status.update(f"Showing suggestions for: '{query}'")
        elif event.suggestion == "HIDE":
            self.popup.hide()
            self.status.update("Autocomplete hidden")
    
    def action_hide_autocomplete(self) -> None:
        """Hide the autocomplete popup."""
        self.popup.hide()
        self.autocomplete_input._hide_autocomplete()
    
    def action_select_suggestion(self) -> None:
        """Select the highlighted suggestion."""
        if self.popup.visible:
            suggestion = self.popup.get_selected_suggestion()
            if suggestion:
                self.autocomplete_input.insert_suggestion(suggestion)
                self.status.update(f"Selected: {suggestion}")
    
    def action_move_up(self) -> None:
        """Move selection up in the autocomplete list."""
        if self.popup.visible:
            self.popup.suggestions_list.action_cursor_up()
            suggestion = self.popup.get_selected_suggestion()
            if suggestion:
                # Only replace the current mention span, not the whole input
                self.autocomplete_input.preview_suggestion(suggestion)
    
    def action_move_down(self) -> None:
        """Move selection down in the autocomplete list."""
        if self.popup.visible:
            self.popup.suggestions_list.action_cursor_down()
            suggestion = self.popup.get_selected_suggestion()
            if suggestion:
                # Only replace the current mention span, not the whole input
                self.autocomplete_input.preview_suggestion(suggestion)
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list item selection with mouse/enter."""
        if event.list_view == self.popup.suggestions_list:
            suggestion = self.popup.get_selected_suggestion()
            if suggestion:
                self.autocomplete_input.insert_suggestion(suggestion)
                self.status.update(f"Selected: @{suggestion}")
