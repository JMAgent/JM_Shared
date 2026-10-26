"""
LEARNER IMPLEMENTATION — Assignment OCT1 Refund Desk

Implement every function below. The auto-grader imports:
  import src.refund_ops

No API key is required. Do not call a live chat model from these functions.
Do not copy secrets from class demos into this repository.
"""
from __future__ import annotations

from typing import Any , TypedDict, Annotated
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command
from langchain_groq import ChatGroq
from langchain.tools import tool
from dotenv import load_dotenv
import os
import operator
import uuid
import sqlite3
from mcp.server.fastmcp import FastMCP



#class RefundEstimate:  # replace with a pydantic BaseModel
#    """amount: int, fee: float, net: float, note: str"""

class RefundEstimate (BaseModel):
    """amount: int, fee: float, net: float, note: str"""
    amount : int =Field(description = "amount paid ")
    fee : float = Field(description = "admin fees for processing")
    net : float = Field(description = "net amount")
    note : str = Field(description = "notes about the order processed")



def estimate_refund(amount: int) -> str:
    """
    Illustrative 2% processing fee.

    fee = round(amount * 0.02, 2)
    net = round(amount - fee, 2)

    Return exactly:
      "Original amount: INR {amount}, illustrative processing fee: INR {fee}, net amount: INR {net}"
    """
    fee = round(amount * 0.02, 2)
    net = round(amount - fee, 2)
    return f"Original amount: INR {amount}, illustrative processing fee: INR {fee}, net amount: INR {net}"


def estimate_model(amount: int) -> Any:
    """
    Return a RefundEstimate for amount.
    fee and net use the same rounding as estimate_refund.
    note must contain the word "hypothetical" (any casing is fine, but include the word).
    """
    Refund_Estimate = RefundEstimate()

    Refund_Estimate.amount = amount
    Refund_Estimate.fee = round(amount * 0.02, 2)
    Refund_Estimate.net = round(amount - Refund_Estimate.fee , 2)
    Refund_Estimate.note = "hypothetical estimated refund is provided"  
 
    return Refund_Estimate


def build_conversation(question: str, answer: str, followup: str) -> list:
    """
    Return four LangChain messages, in this order:
      1. SystemMessage content exactly:
         "You are a helpful assistant that answers every question with a joke."
      2. HumanMessage content = question
      3. AIMessage content = answer
      4. HumanMessage content = followup
    """    
    # 1. System Message
    Systemmessage = SystemMessage(content="You are a helpful assistant that answers every question with a joke.")

    # 2. User Message
    Humanmessage_1 = HumanMessage(content=f"{question}")
    AIMessage_1  = AIMessage(content=f"{answer}")
    Humanmessage_2 = HumanMessage(content=f"{followup}")

    messages =[Systemmessage, Humanmessage_1, AIMessage_1, Humanmessage_2 ]   

    return messages
    

def refund_prompt(amount: int, reason: str) -> str:
    """
    Build a ChatPromptTemplate with:
      system: "You are a refund assistant. Explain that the fee is hypothetical."
      human:  "Amount: {amount}\\nReason: {reason}"

    Invoke it with amount and reason. Return one string that contains the
    rendered amount, the reason, and the word "hypothetical".
    """
    
    chat_template = ChatPromptTemplate.from_messages (
        [
          ("system", "You are a refund assistant. Explain that the fee is hypothetical."),
          ("human", f"Amount: {amount}\\nReason: {reason}"),
              
        ]
        )
    prompt = chat_template.invoke({"prompt": "Prepare a one line statement for the refund  amount, and the given reason, and includethe word 'hypothetical' in your statement."})
    return prompt
    

def apply_tool_result(tool_name: str, args: dict, tool_call_id: str) -> Any:
    """
    Run a tool and wrap the result in a ToolMessage.

    tool_name "add": content is str(int(args["a"]) + int(args["b"]))
    tool_name "estimate_refund": content is estimate_refund(int(args["amount"]))
    any other name: raise KeyError

    Set tool_call_id on the ToolMessage.
    """
    conversation =""
    if tool_name == "add":
        tool_result = str(int(args["a"]) + int(args["b"]))             
         
    elif tool_name == "estimate_refund":
        tool_result = estimate_refund(int(args["amount"]))         
    else :
        tool_message = ""
        raise KeyError("Invalid Tool Name")
    
    tool_message = conversation + str(f"ToolMessage(content=str({tool_result}),tool_call_id={tool_call_id},name={tool_name})")
    
    return tool_message    




# step 1 -  Define the state
class FoodState(TypedDict):
    city: str
    question: str
    favorite_food: str
# step 2 - Define the node
def prepare_question(state: FoodState):
    return {"question": f"What is the favorite food of {state['city']}"}

def answer(state: FoodState):
    if state['city'] == 'Mumbai':
        return {"favorite_food" : "Vada Pav"}
    elif state['city'] == 'Delhi':
        return {"favorite_food" : "Chaat"} 
    elif state['city'] == 'Mysore':
        return {"favorite_food" : "Mysore Pak"}            
    else : 
        return {"favorite_food" : "Unknown"}  
  
def build_food_graph() -> Any:
    """
    Compiled LangGraph.

    State keys: city, question, favorite_food.
    prepare node sets question to "What is the favorite food of {city}?"
    answer node sets favorite_food:
      Mumbai -> Vada Pav
      Delhi -> Chaat
      Mysore -> Mysore Pak
      anything else -> Unknown

    START -> prepare -> answer -> END
    """

    # step 3 - Define the graph

    builder = StateGraph(FoodState)
    builder.add_node('prepare_question', prepare_question)
    builder.add_node('answer', answer)

    # step 4 - connect the nodes

    builder.add_edge(START, 'prepare_question')
    builder.add_edge('prepare_question', 'answer')
    builder.add_edge('answer',END)

    # step 5 - compile the graph

    graph = builder.compile()
    #graph structure
    graph.get_graph().print_ascii()
    # step 6 - run the graph
    return graph

# step 1 -  Define the state
class SupportState(TypedDict):
    text: str
    priority: str
    response: str
    log : Annotated[list[str], operator.add] 

# step 2 - Define the node
def classify(state: SupportState):
    if "urgent" in state["text"].lower():
        priority = "urgent"
    else:
        priority = "normal"
    return {
        "priority": priority,
        "log": [f"Ticket classified as {priority}"],
    }

def urgent(state: SupportState):
    print("Ticket has been escalated to the urgent support team.")
    return {
        "response": "Ticket has been escalated to the urgent support team.",
        "log": ["Ticket escalated to urgent support"],
    }

def normal(state: SupportState):
    print("Thank you for contacting support. We will get back to you shortly.")
    return {
        "response": "Thank you for contacting support. We will get back to you shortly.",
        "log": ["Normal support provided"],
    }

def classify_ticket(state: SupportState):
    return state["priority"]


def build_support_graph():
    """
    Compiled LangGraph with a list reducer on log.

    State keys: text, priority, response, log.
    log is Annotated[list[str], operator.add].

    classify: priority "urgent" if "urgent" is in text.lower(), else "normal".
    Return log item "Ticket classified as {priority}".
    Do not mutate state["log"] in place.

    conditional edge:
      "urgent" -> urgent support response
        "Ticket has been escalated to the urgent support team."
        log item "Ticket escalated to urgent support"
      "normal" -> normal support response
        "Thank you for contacting support. We will get back to you shortly."
        log item "Normal support provided"

    Callers pass log: [] on invoke.
    """
     # step 3 - Define the graph
    
    builder = StateGraph(SupportState)
    builder.add_node('classify', classify)
    builder.add_node('urgent', urgent)
    builder.add_node('normal', normal)

    # step 4 - connect the nodes
    
    builder.add_edge(START, 'classify')
    builder.add_conditional_edges("classify", classify_ticket,
    {
    "urgent": "urgent",
    "normal": "normal"
    })
    builder.add_edge('urgent',END)
    builder.add_edge('normal',END)

    # step 5 - compile the graph
    
    graph = builder.compile()
    #graph structure
    graph.get_graph().print_ascii()
    # step 6 - run the graph
    return graph
    

#Step 1 : Define the State
class ReviewLoopState(TypedDict):
    draft: str
    attempts: int
    history: Annotated[list[str], operator.add]    

#Step 2 : Define the Nodes
def write_node(state : ReviewLoopState):
  attempt = state["attempts"] +1
  if  attempt == 1:
    d = "LangGraph"
  elif attempt > 1 :
    d = "LangGraph orchestrates stateful AI workflows with nodes, edges, and checkpointing."
  return {
            "draft" : d,
            "attempts" : attempt,
            "history" :  [f"Draft attempt {attempt}"],
        }

def evaluate_node(state : ReviewLoopState):
  if len(state["draft"].split()) >= 8 :
    return{
              "history" : ["Quality check passed: true"]
          }
  else :
    return{
            "history" : ["Quality check passed: false"]
          }

def route_after_evaluate(state: ReviewLoopState):
    if len(state["draft"].split()) >= 8 or state["attempts"] >= 3:
        return "done"
    return "write"

def done(state: ReviewLoopState):
    return(state)

def build_review_loop():
    
    """
    Compiled LangGraph review loop.

    State keys: draft, attempts, history.
    history is Annotated[list[str], operator.add].

    write node:
      attempt = attempts + 1 (missing attempts counts as 0)
      attempt 1 draft is exactly "LangGraph"
      later drafts are exactly:
        "LangGraph orchestrates stateful AI workflows with nodes, edges, and checkpointing."
      history item: "Draft attempt {attempt}"

    evaluate node appends history item "Quality check passed: {true/false}"
    where the check is len(draft.split()) >= 8.

    After evaluate:
      finish when the draft has at least 8 words, or attempts >= 3
      otherwise go back to write

    Callers pass draft="", attempts=0, history=[].
    """  
    #Step 3 : Define the Nodes
    builder = StateGraph(ReviewLoopState)
    builder.add_node('write', write_node)
    builder.add_node('evaluate', evaluate_node)
    #builder.add_node('post', route_after_evaluate)

    #Step 4 : Connect the Nodes
    builder.add_edge(START,'write')
    builder.add_edge('write','evaluate')
    builder.add_conditional_edges('evaluate', route_after_evaluate,
    {'write': 'write',
    'done': END},
    )

    #Step 5 : Compile the graph.

    graph = builder.compile()
    graph.get_graph().print_ascii()
    return(graph)


#Step 1 : Define the State 
class refundgraph(TypedDict):
    request_id:str
    amount : float
    reason : str 
    decision : str
    status : str
    audit : Annotated[list[str], operator.add]

#Step 2 : Define the Nodes
def validate_request(state:refundgraph):
    amount = state["amount"]
    if amount < 0:
        raise ValueError("Refund amount must be greater than 0")
    else :
        return {
            "audit" : [f"Validation: amount {amount} is valid"]
        }

def route_after_validate(state:refundgraph):
    if state["amount"] < 1000 :
      return "automatic_approval"
    else :
      return "manager_review"

def automatic_approval(state:refundgraph):
    amount = state["amount"]
    return {
      "decision" : "approved",
      "audit" : [f"Automatic Approval: amount {amount} is approved"],        
    }

def manager_review(state:refundgraph):
    human_response = interrupt({
            "question": "Do you approve this refund?",
            "request_id": state["request_id"],
            "amount": state["amount"],
            "reason": state["reason"],
          })
    amount = state["amount"]
    if (type(human_response) == dict) and (human_response.get("manager") == "approved"):
        decision ="approved"
    else:
        decision ="rejected"
    return {
        "decision":decision,
        "audit": [f"Manager Review: amount {amount} , Approval is {human_response}"]
        
    }

def post_manager_review(state:refundgraph):
    decision = state["decision"]
    if decision == "approved":
        return "execute_refund"
    else :
        return "reject_refund"
 
def execute_refund(state:refundgraph):
    amount = state["amount"]
    return{
        "status":"completed",
        "audit":[f"Execute Refund: amount {amount} is executed"],
    }

def reject_refund(state:refundgraph):
    amount = state["amount"]
    return{
        "status":"rejected",
        "audit":[f"Reject Refund: amount {amount} is rejected"],
    }



def build_refund_graph(checkpointer):
    """
    Compiled refund graph. Pass checkpointer to compile().

    State keys: request_id, amount, reason, decision, status, audit.
    audit is Annotated[list[str], operator.add]. Callers pass audit: [].

    validate_request:
      if amount <= 0: raise ValueError("Refund amount must be greater than 0")
      else audit item "Validation: amount {amount} is valid"

    Route after validate:
      amount < 1000 -> automatic_approval
      else -> manager_review

    automatic_approval:
      decision "approved"
      audit item "Automatic Approval: amount {amount} is approved"
      then execute_refund

    manager_review:
      human_response = interrupt({
        "question": "Do you approve this refund?",
        "request_id": state["request_id"],
        "amount": state["amount"],
        "reason": state["reason"],
      })
      decision "approved" only when human_response is a dict and
      human_response.get("manager") == "approved"; otherwise "rejected"
      audit item "Manager Review: amount {amount} , Approval is {human_response}"

    After manager review:
      approved -> execute_refund
      otherwise -> reject_refund

    execute_refund: status "completed",
      audit item "Execute Refund: amount {amount} is executed"
    reject_refund: status "rejected",
      audit item "Reject Refund: amount {amount} is rejected"

    Do not perform a non-idempotent side effect before interrupt().
    """
    #Step 3 : Define the Graph and add nodes
    builder4 = StateGraph(refundgraph)
    builder4.add_node('validate_request',validate_request)
    #builder4.add_node('route_after_validate',route_after_validate)
    builder4.add_node('automatic_approval',automatic_approval)
    builder4.add_node('manager_review',manager_review)
    #builder4.add_node('post_manager_review',post_manager_review)
    builder4.add_node('execute_refund',execute_refund)
    builder4.add_node('reject_refund',reject_refund)

    #Step 4 : Connect the nodes
    builder4.add_edge(START,'validate_request')
    builder4.add_conditional_edges('validate_request',route_after_validate,
                                {'automatic_approval' : 'automatic_approval',
                                 'manager_review' : 'manager_review',
                                }
                                  )
    builder4.add_edge('automatic_approval','execute_refund')
    builder4.add_conditional_edges(
      'manager_review',
      post_manager_review,
      {
        'execute_refund': 'execute_refund',
        'reject_refund': 'reject_refund',
      },
    )

    builder4.add_edge('execute_refund',END)
    builder4.add_edge('reject_refund',END)

    #Step 5 : Compile the graph
    
    graph4 = builder4.compile(checkpointer = checkpointer)
    #config_1 = {"configurable" : {"thread_id" : "1"}}
    graph4.get_graph().print_ascii()
    return(graph4)


def make_sqlite_checkpointer(db_path: str):
    """
    Return a live SqliteSaver for db_path.
    Use sqlite3.connect(db_path, check_same_thread=False).
    Keep the connection open on the returned saver.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)
    print("SQLite checkpoint should still be waiting on the manager review")
    return memory


def build_mcp_server():
    """
    Return a FastMCP server named "Refund Desk" with:

    Tools
      add(a: int, b: int) -> int
      estimate_refund(amount: int) -> str   (same string as estimate_refund())
      Use @mcp.tool(name="estimate_refund") if the function cannot use that name.

    Resources
      resource://greeting -> "Hello from FastMCP Resources!"
      data://config -> JSON string with "theme": "dark" and features including "tools"

    Prompt
      ask_about_topic(topic: str) -> a string that contains topic
    """
    mcp = FastMCP("Refund Desk")

    @mcp.tool()
    async def add(a: int, b: int) -> int:
        return (a+b)

    @mcp.tool()
    async def estimate_refund(amount: int) -> str:
        estimate_refund()
        
      
