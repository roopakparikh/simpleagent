import os, json, time, ast, math, getpass
import uuid, threading, asyncio
import sys
from pathlib import Path
from typing import Dict, List, Callable, Any, TypedDict, Literal

# LangGraph / LangChain (Anthropic)
from langgraph.graph import StateGraph, START, END
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
import logging
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient


log = logging.getLogger(__name__)

class GraphState(TypedDict, total=False):
    task: str
    plan: str
    scratch: List[str]
    evidence: List[str]
    result: str
    step: int
    done: bool



def _normalize_tools(tools_param: Any) -> Dict[str, Any]:
    """Accept dict, list, or tuple of tools and return name->tool mapping.
    Supports LangChain tools (with .name) and plain callables.
    """
    if tools_param is None:
        return {}
    if isinstance(tools_param, dict):
        return dict(tools_param)
    if isinstance(tools_param, (list, tuple)):
        out: Dict[str, Any] = {}
        for i, t in enumerate(tools_param):
            name = getattr(t, "name", None) or getattr(t, "__name__", None) or f"tool_{i}"
            out[str(name)] = t
        return out
    # Fallback: single callable or tool object
    name = getattr(tools_param, "name", None) or getattr(tools_param, "__name__", None) or "tool"
    return {str(name): tools_param}

@tool
async def dosleep(seconds: int) -> str:
  ''' Sleep asynchronously for the specified seconds '''
  await asyncio.sleep(int(seconds))
  return f"Slept for {seconds} seconds"

class AgentGraph:

    def __init__(self, llm, mcpservers):
        self.mcpservers = mcpservers
        self.llm = llm
        self.system_prompt = (
            "You are GraphAgent, a principled planner-executor. "
            "Prefer structured, concise outputs; use provided tools preferentially."
            " Some tools may return a task or operation id, that should be checked again"
            " after sleeping for some time using dosleep tool"
        )
        self.llm.set_system_prompt(self.system_prompt)
    
    def _node_plan(self, state: GraphState) -> GraphState:
        log.debug(f"node_plan: task='{state.get('task','')[:80]}'")
        prompt = f"""Plan step-by-step to solve the user task.
            Task: {state.get('task','')}
            Return JSON: {{"subtasks": ["..."], "tools": {{"search": true/false, "math": true/false}}, "success_criteria": ["..."]}}"""
        js = self.llm.call_llm(prompt)
        try:
            plan = json.loads(js[js.find("{"): js.rfind("}")+1])
        except Exception:
            plan = {"subtasks": ["write", "tools"], "success_criteria": ["clear answer"]}
        plan_str = json.dumps(plan, indent=2)
        scratch = (state.get("scratch") or []) + ["PLAN:\n" + plan_str]
        log.debug(f"node_plan: produced plan with {len(plan.get('subtasks', []))} subtasks")
        return {"plan": plan_str, "scratch": scratch}

    def _node_route_decider(self, state: GraphState) -> Literal["tools", "write"]:
        log.debug("node_route_decider: deciding next node")
        prompt = f"""You are a router. Decide next node.
            Context scratch:\n{chr(10).join((state.get('scratch') or [])[-5:])}
            If you want to call a specific tool -> 'tools'. If ready -> 'write'.
            Return one token from [tools, write]. Task: {state.get('task','')}"""
        choice = self.llm.call_llm(prompt).lower()
        if "tool" in choice:
            log.debug("node_route_decider: chose 'tools'")
            return "tools"
        log.debug("node_route_decider: chose 'write'")
        return "write"

    def _node_write(self, state: GraphState) -> GraphState:
        log.debug("node_write: drafting final answer")
        prompt = f"""Write the final answer.
    Task: {state.get('task','')}
    Use the evidence and any math results below, cite inline like [1],[2].
    Evidence:\n{chr(10).join(f'[{i+1}] '+e for i,e in enumerate(state.get('evidence') or []))}
    Notes:\n{chr(10).join((state.get('scratch') or [])[-5:])}
    Return a concise, structured answer."""
        draft = self.llm.call_llm(prompt, temperature=0.3)
        sc = (state.get("scratch") or []) + ["DRAFT:\n" + draft]
        log.debug(f"node_write: draft length={len(draft)}")
        return {"result": draft, "scratch": sc}


    async def _node_tools(self, state: GraphState, tools: Dict[str, Any]) -> GraphState:
        """Async tool-calling node that supports both MCP/LangChain tools and local callables.
        
        Handles long-running tools by making the entire node async.
        """
        log.debug(f"node_tools: available={list(tools.keys())}")
        available = list(tools.keys())
        tool_list = ", ".join(available) if available else "(none)"
        
        # Check if we've made too many tool calls without progress
        step = state.get("step", 0) + 1
        if step > 10:
            log.debug("node_tools: too many steps, forcing write")
            return {"scratch": (state.get("scratch") or []) + ["MAX_STEPS: Forcing completion"], "done": True, "step": step}
        
        prompt = f"""You may call exactly one tool from the available tools or return none.
    Task: {state.get('task','')}
    Recent notes:\n{chr(10).join((state.get('scratch') or [])[-5:])}
    Available tools: {tool_list}
    Step: {step}/10
    Return strict JSON: {{"tool": "<name|none>", "args": {{}}}}"""
        js = self.llm.call_llm(prompt)
        try:
            spec = json.loads(js[js.find("{"):js.rfind("}")+1])
        except Exception as e:
            log.debug(f"node_tools: error parsing JSON {e}")
            spec = {"tool": "none", "args": {}}
        tool_name = str(spec.get("tool") or "none").strip()
        args = spec.get("args") or {}

        scratch = (state.get("scratch") or []) + [f"STEP-{step}: Considering tool '{tool_name}'"]

        if tool_name == "none" or tool_name not in tools:
            msg = f"TOOL: none or unavailable ({tool_name}). Moving to write."
            log.debug(f"node_tools: {msg}")
            return {"scratch": scratch + [msg], "done": True, "step": step}

        try:
            tool_obj = tools[tool_name]
            log.debug(f"node_tools: invoking '{tool_name}' with args={args}")

            # Case A: LangChain/MCP tool (async)
            if hasattr(tool_obj, "ainvoke"):
                res = await tool_obj.ainvoke(args)
                log.debug(f"node_tools: async result={str(res)[:200]}")
                return {"scratch": scratch + [f"TOOL-CALL: {tool_name}({args}) -> {res}"], "step": step}
            
            # Case B: LangChain/MCP tool (sync)
            elif hasattr(tool_obj, "invoke"):
                res = tool_obj.invoke(args)
                log.debug(f"node_tools: sync result={str(res)[:200]}")
                return {"scratch": scratch + [f"TOOL-CALL: {tool_name}({args}) -> {res}"], "step": step}
            
            # Case C: Local callable
            elif callable(tool_obj):
                try:
                    # Try async first
                    if asyncio.iscoroutinefunction(tool_obj):
                        res = await tool_obj(args, state)
                    else:
                        res = tool_obj(args, state)
                except TypeError:
                    # Fallback patterns
                    if asyncio.iscoroutinefunction(tool_obj):
                        res = await tool_obj(**args if isinstance(args, dict) else {"args": args})
                    else:
                        res = tool_obj(**args if isinstance(args, dict) else {"args": args})
                
                if isinstance(res, dict):
                    out = dict(res)
                    out["scratch"] = (res.get("scratch") or scratch) + [f"TOOL-CALL: {tool_name}({args}) -> dict result"]
                    out["step"] = step
                    return out
                else:
                    return {"scratch": scratch + [f"TOOL-CALL: {tool_name}({args}) -> {res}"], "step": step}
            
            else:
                return {"scratch": scratch + [f"TOOL-ERROR: {tool_name} invalid tool type"], "step": step}
                
        except Exception as e:
            log.debug(f"node_tools: error calling '{tool_name}': {e}")
            return {"scratch": scratch + [f"TOOL-ERROR: {tool_name}({args}) -> {e}"], "step": step}

    async def init(self):
        await self._load_mcp_tools()
        g = StateGraph(GraphState)

        # Wrap nodes to capture llm
        g.add_node("plan", lambda s: self._node_plan(s))
        # Route is a pass-through node; decision is made in conditional edges
        g.add_node("route", lambda s: s)
        g.add_node("write", lambda s: self._node_write(s))
        # Tools node (generic tool execution)
        all_tools = self.mcp_tools.copy()
        all_tools.append(dosleep)
        tools = _normalize_tools(all_tools)
        # For async nodes in LangGraph, we need to make the wrapper async
        async def tools_wrapper(s):
            return await self._node_tools(s, tools)
        g.add_node("tools", tools_wrapper)

        g.add_edge(START, "plan")
        g.add_edge("plan", "route")

        # Router as conditional edges from a lightweight node name "route"
        def router(s: GraphState) -> Literal["tools", "write", "end"]:
            # Check termination conditions first
            if s.get("done") or s.get("result"):
                return "end"
            
            # Check step limit to prevent infinite loops
            step = s.get("step", 0)
            if step >= 8:  # Lower limit to prevent recursion
                log.debug(f"router: step limit reached ({step}), forcing write")
                return "write"
            
            # Decide next using LLM
            choice = self._node_route_decider(s)
            log.debug(f"router: choice={choice} (step={step})")
            return choice

        g.add_conditional_edges(
            "route",
            router,
            {
                "tools": "tools",
                "write": "write",
                "end": END,
            },
        )

        # After work nodes, go back to router or to critic
        g.add_edge("tools", "route")
        g.add_edge("write", END)
        return g.compile(checkpointer=None, interrupt_before=[], interrupt_after=[], debug=False)

    async def _load_mcp_tools(self):
        self.mcp_client = MultiServerMCPClient(connections=self.mcpservers)
        tools = await self.mcp_client.get_tools()
        self.mcp_tools = tools

    async def run(self, task: str):
        app = await self.init()
        init: GraphState = {
                "task": task,
                "plan": "",
                "scratch": [],
                "evidence": [],
                "result": "",
                "step": 0,
                "done": False,
        }
        # Use async invoke for async nodes
        out: GraphState = await app.ainvoke(init)
        return out.get('result', '')